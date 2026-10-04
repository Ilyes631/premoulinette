"""Project ingestion: every analysis works on a fresh, bounded copy (a *snapshot*) of the project.

The student's folder is never analyzed in place and never modified. Three sources are supported:

* a local folder (``snapshot_from_path``): walked without following links (symlinks, junctions,
  reparse points are skipped), then copied file by file;
* a zip archive (``snapshot_from_zip``): every member is validated **before anything is written**
  (absolute / drive / UNC / ``..`` paths reject the archive; symlinks, encrypted members and names
  Windows cannot store are skipped) and the declared sizes are checked against the bomb limits;
  decompression is then streamed with hard caps, so a lying header cannot exceed them either;
* a browser folder upload (``snapshot_from_upload``, ``webkitdirectory`` relative paths), validated
  like zip member names.

Limits (project files, ``.git`` excluded): 5000 files, 50 MB in total, 5 MB per file (bigger files are
skipped and reported). Dependency / tool caches (``node_modules``, ``.venv``, ``venv``, ``env``, ``.tox``,
``.mypy_cache``, ``.pytest_cache``) are not copied: an empty placeholder folder is kept so the structure
check can still flag them. ``__pycache__`` IS copied: it is a diagnostic (unwanted file).
``.git`` directories are copied with their own limits, then neutralized by :func:`sanitize_git_dir`.
"""
from __future__ import annotations

import io
import os
import re
import stat
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Literal

from pydantic import BaseModel, Field

from premoulinette.project.paths import is_link_like, join_rel

MB = 1024 * 1024

MAX_FILES = 5000
MAX_TOTAL_BYTES = 50 * MB
MAX_FILE_BYTES = 5 * MB
MAX_DIRS = 5000
SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache"})

# .git internals have their own (larger) budget: they are needed for git checks only.
GIT_MAX_FILES = 20_000
GIT_MAX_BYTES = 200 * MB

# Zip-specific guards.
ZIP_MAX_MEMBERS = 100_000
ZIP_MAX_RATIO = 200            # per member, for members bigger than ZIP_RATIO_MIN_SIZE
ZIP_RATIO_MIN_SIZE = 1 * MB
ARCHIVE_JUNK_DIRS = frozenset({"__MACOSX"})

_CHUNK = 64 * 1024
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WIN_FORBIDDEN_CHARS = set('<>:"|?*')
_WIN_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    | {f"COM{c}" for c in "¹²³"} | {f"LPT{c}" for c in "¹²³"}
)

SourceKind = Literal["path", "zip", "upload", "demo"]


class Snapshot(BaseModel):
    root: Path                 # absolute path of the snapshot copy (always a fresh copy, never the user's folder)
    source_kind: SourceKind
    source_path: str | None
    name: str
    file_count: int            # project files copied (``.git`` internals excluded)
    total_bytes: int           # bytes of those files
    skipped: list[str] = Field(default_factory=list)    # skipped heavy dirs / too big files / links
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------------------------


def clean_member_path(raw: str) -> str:
    """Normalize an archive / upload relative path to POSIX, rejecting anything that could escape.

    Raises ``ValueError`` for absolute paths, drive letters, UNC paths, ``..`` components, NUL bytes.
    Returns ``""`` for a path that designates the root itself (``"./"``).
    """
    if not isinstance(raw, str):
        raise ValueError("Invalid path in the project: not a string.")
    value = raw.replace("\\", "/")
    if "\x00" in value:
        raise ValueError(f"Invalid path in the project (NUL byte): {raw!r}")
    if value.startswith("/") or _DRIVE_RE.match(value):
        raise ValueError(f"Absolute paths are not allowed in a project: {raw!r}")
    parts = [p for p in value.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"Paths escaping the project folder ('..') are not allowed: {raw!r}")
    return "/".join(parts)


def windows_name_problem(component: str) -> str | None:
    """Why ``component`` cannot be stored safely as a file name (on Windows), or None."""
    if any(ord(ch) < 32 for ch in component):
        return "control character in the name"
    bad = sorted({ch for ch in component if ch in _WIN_FORBIDDEN_CHARS})
    if bad:
        return f"character(s) {' '.join(bad)} not allowed in file names"
    if component.endswith((" ", ".")):
        return "name ending with a space or a dot"
    stem = component.split(".", 1)[0].rstrip(" ").upper()
    if stem in _WIN_RESERVED:
        return f"reserved device name '{stem}'"
    return None


# ---------------------------------------------------------------------------------------------
# Planning: decide what to copy, enforce limits BEFORE writing anything
# ---------------------------------------------------------------------------------------------


@dataclass
class _Item:
    rel: str
    size: int
    open: Callable[[], BinaryIO]
    git: bool = False


@dataclass
class _Plan:
    files: list[_Item] = field(default_factory=list)
    dirs: set[str] = field(default_factory=set)
    placeholders: set[str] = field(default_factory=set)   # skipped dependency dirs (kept empty)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    project_files: int = 0
    project_bytes: int = 0
    project_dirs: int = 0
    git_files: int = 0
    git_bytes: int = 0
    git_overflow: bool = False
    _seen: dict[str, str] = field(default_factory=dict)     # casefolded path -> actual path
    _file_paths: set[str] = field(default_factory=set)
    _skip_notes: set[str] = field(default_factory=set)
    _top_counts: dict[str, int] = field(default_factory=dict)

    # ---- classification -----------------------------------------------------------------------
    def classify(self, rel: str, *, is_dir: bool) -> Literal["keep", "git", "skip"]:
        """Decide what to do with a path (records skip notes). Never raises."""
        parts = rel.split("/")
        dir_parts = parts if is_dir else parts[:-1]
        for i, part in enumerate(dir_parts):
            if part == ".git":
                return "git"
            if part in SKIP_DIRS:
                skipped_dir = "/".join(parts[: i + 1])
                self.placeholders.add(skipped_dir)
                self._skip(f"{skipped_dir}/ (dependency/cache folder, not copied)")
                return "skip"
            if part in ARCHIVE_JUNK_DIRS:
                self._skip(f"{'/'.join(parts[: i + 1])}/ (archive metadata, not part of the project)")
                return "skip"
        if not is_dir and parts[-1] == ".git":
            self._skip(f"{rel} (git link file pointing outside the project, not copied)")
            self.warnings.append(
                f"'{rel}' is a git link (submodule or worktree) pointing outside the project: it was not copied."
            )
            return "skip"
        return "keep"

    def _skip(self, note: str) -> None:
        if note not in self._skip_notes:
            self._skip_notes.add(note)
            self.skipped.append(note)

    def _conflict(self, rel: str, *, is_dir: bool) -> str | None:
        """Case-insensitive collision or file/folder conflict for ``rel`` or one of its parents.

        Such paths cannot coexist on Windows/macOS: writing them would silently merge or overwrite files.
        """
        for parent in _parents(rel):
            if parent in self._file_paths:
                return f"its parent '{parent}' is a file"
            previous = self._seen.get(parent.casefold())
            if previous is not None and previous != parent:
                return f"folder '{parent}' differs only by letter case from '{previous}'"
        previous = self._seen.get(rel.casefold())
        if previous is None:
            return None
        if previous == rel:
            if is_dir and rel not in self._file_paths:
                return None
            return "duplicate entry"
        return f"differs only by letter case from '{previous}'"

    def _register(self, rel: str, *, is_dir: bool) -> None:
        for parent in _parents(rel):
            self._seen.setdefault(parent.casefold(), parent)
        self._seen.setdefault(rel.casefold(), rel)
        if not is_dir:
            self._file_paths.add(rel)

    def _reject_conflict(self, rel: str, reason: str) -> None:
        self._skip(f"{rel} ({reason}, not copied)")
        self.warnings.append(
            f"'{rel}' was not copied: {reason}. Windows and macOS cannot store both, but on the grader (Linux) "
            "they are different paths: check which one you really want."
        )

    def add_dir(self, rel: str) -> None:
        if not rel or rel in self.dirs:
            return
        kind = self.classify(rel, is_dir=True)
        if kind == "skip":
            return
        if kind == "keep":
            reason = self._conflict(rel, is_dir=True)
            if reason:
                self._reject_conflict(rel, reason)
                return
            self._register(rel, is_dir=True)
            self.project_dirs += 1
            if self.project_dirs > MAX_DIRS:
                raise ValueError(f"The project contains too many folders (more than {MAX_DIRS}). Did you select the right folder?")
        for parent in _parents(rel):
            self.dirs.add(parent)
        self.dirs.add(rel)

    def add_file(self, rel: str, size: int, opener: Callable[[], BinaryIO]) -> None:
        kind = self.classify(rel, is_dir=False)
        if kind == "skip":
            return
        if kind == "git":
            if self.git_overflow:
                return
            self.git_files += 1
            self.git_bytes += size
            if self.git_files > GIT_MAX_FILES or self.git_bytes > GIT_MAX_BYTES:
                self.git_overflow = True
                return
            self.files.append(_Item(rel, size, opener, git=True))
            return
        reason = self._conflict(rel, is_dir=False)
        if reason:
            self._reject_conflict(rel, reason)
            return
        self._register(rel, is_dir=False)
        if size > MAX_FILE_BYTES:
            self._skip(f"{rel} (file too large: {size / MB:.1f} MB, limit {MAX_FILE_BYTES // MB} MB)")
            return
        self.project_files += 1
        self.project_bytes += size
        top = rel.split("/", 1)[0]
        self._top_counts[top] = self._top_counts.get(top, 0) + 1
        if self.project_files > MAX_FILES:
            raise ValueError(
                f"The project contains too many files (more than {MAX_FILES}). Did you select the right folder?"
                + self._heaviest()
            )
        if self.project_bytes > MAX_TOTAL_BYTES:
            raise ValueError(
                f"The project is too large (more than {MAX_TOTAL_BYTES // MB} MB of files). "
                "Did you select the right folder?" + self._heaviest()
            )
        self.files.append(_Item(rel, size, opener))
        for parent in _parents(rel):
            self.dirs.add(parent)

    def _heaviest(self) -> str:
        top = sorted(self._top_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        if not top:
            return ""
        return " Biggest entries: " + ", ".join(f"{name} ({count} files)" for name, count in top) + "."

    def finish(self) -> None:
        if self.git_overflow:
            self.files = [f for f in self.files if not f.git]
            self.dirs = {d for d in self.dirs if ".git" not in d.split("/")}
            self._skip(".git/ (repository history too large to copy)")
            self.warnings.append(
                f"The .git folder is larger than {GIT_MAX_FILES} files / {GIT_MAX_BYTES // MB} MB: "
                "it was not copied, so git checks (tracked / ignored / uncommitted files) are skipped."
            )


def _parents(rel: str) -> list[str]:
    parts = rel.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


# ---------------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------------


def _prepare_dest(dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists():
        if not dest.is_dir() or any(dest.iterdir()):
            raise ValueError(f"The snapshot destination already exists and is not empty: {dest}")
    else:
        dest.mkdir(parents=True)
    return dest.resolve()


def _target(dest: Path, rel: str) -> Path:
    target = dest.joinpath(*rel.split("/"))
    # Defense in depth: components were validated, the resolved target must stay inside dest.
    if not os.path.abspath(target).startswith(str(dest) + os.sep):
        raise ValueError(f"Refusing to write outside the snapshot: {rel!r}")
    return target


def _write_plan(plan: _Plan, dest: Path) -> tuple[int, int]:
    plan.finish()
    for rel in sorted(plan.dirs | plan.placeholders, key=lambda p: (p.count("/"), p)):
        try:
            _target(dest, rel).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            plan.warnings.append(f"Folder '{rel}' could not be created in the snapshot: {exc.strerror or exc}")
    files = 0
    total = 0
    for item in plan.files:
        target = _target(dest, item.rel)
        limit = (GIT_MAX_BYTES if item.git else MAX_FILE_BYTES)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            written = _copy_stream(item, target, limit)
        except _TooLarge:
            _unlink(target)
            plan._skip(f"{item.rel} (file grew beyond the limit while copying)")
            continue
        except OSError as exc:
            _unlink(target)
            plan._skip(f"{item.rel} (could not be copied: {exc.strerror or exc})")
            if not item.git:
                plan.warnings.append(f"'{item.rel}' could not be copied ({exc.strerror or exc}): it is missing from the analysis.")
            continue
        if not item.git:
            files += 1
            total += written
    return files, total


class _TooLarge(Exception):
    pass


def _copy_stream(item: _Item, target: Path, limit: int) -> int:
    written = 0
    with item.open() as src, open(target, "xb") as out:
        while True:
            chunk = src.read(_CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                raise _TooLarge()
            out.write(chunk)
    return written


def _unlink(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()
    except OSError:
        pass


def _discard(dest: Path) -> None:
    """Remove a partially written snapshot (only what this module created inside ``dest``)."""
    if not dest.is_dir():
        return
    _clear_dir(dest)


def _finish(plan: _Plan, dest: Path, *, kind: SourceKind, source: str | None, name: str) -> Snapshot:
    try:
        files, total = _write_plan(plan, dest)
        if any(".git" in d.split("/") for d in plan.dirs):
            sanitize_git_dir(dest)
    except BaseException:
        _discard(dest)
        raise
    return Snapshot(
        root=dest, source_kind=kind, source_path=source, name=name, file_count=files, total_bytes=total,
        skipped=list(plan.skipped), warnings=list(dict.fromkeys(plan.warnings)),
    )


# ---------------------------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------------------------


def snapshot_from_path(src: Path, dest: Path, *, kind: SourceKind = "path") -> Snapshot:
    """Copy a local folder into ``dest`` (links never followed, limits enforced before copying)."""
    src_path = Path(src).expanduser()
    if not src_path.exists():
        raise FileNotFoundError(f"Folder not found: {src}")
    if not src_path.is_dir():
        raise NotADirectoryError(f"Not a folder: {src}")
    src_real = src_path.resolve(strict=True)
    dest_abs = Path(os.path.abspath(dest))
    if dest_abs == src_real or dest_abs.is_relative_to(src_real):
        raise ValueError("The snapshot destination is inside the project folder: choose the project folder itself.")

    plan = _Plan()
    for rel, entry, is_dir in _walk(src_real, plan):
        if is_dir:
            plan.add_dir(rel)
        else:
            try:
                size = entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                plan._skip(f"{rel} (unreadable: {exc.strerror or exc})")
                continue
            plan.add_file(rel, size, _file_opener(entry.path))

    warnings_extra = _outer_repo_warning(src_real) if kind == "path" else []
    dest_root = _prepare_dest(dest)
    plan.warnings.extend(warnings_extra)
    return _finish(plan, dest_root, kind=kind, source=str(src_real), name=src_real.name or str(src_real))


def _file_opener(path: str) -> Callable[[], BinaryIO]:
    def _open() -> BinaryIO:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise OSError(f"not a regular file: {path}")
        except BaseException:
            os.close(fd)
            raise
        return os.fdopen(fd, "rb")
    return _open


def _walk(root: Path, plan: _Plan) -> Iterator[tuple[str, os.DirEntry[str], bool]]:
    """Breadth-first walk, never following links; skipped dirs are not descended into."""
    pending = [""]
    while pending:
        rel_dir = pending.pop()
        try:
            with os.scandir(root / rel_dir if rel_dir else root) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as exc:
            if rel_dir:
                plan._skip(f"{rel_dir}/ (unreadable: {exc.strerror or exc})")
                continue
            raise
        for entry in entries:
            rel = join_rel(rel_dir, entry.name)
            if is_link_like(entry):
                plan._skip(f"{rel} (symbolic link or junction, not followed)")
                continue
            problem = windows_name_problem(entry.name) if os.name != "nt" else None
            if problem:
                plan._skip(f"{rel} ({problem}, not copied)")
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if plan.classify(rel, is_dir=True) == "skip":
                        continue
                    yield rel, entry, True
                    pending.append(rel)
                elif entry.is_file(follow_symlinks=False):
                    yield rel, entry, False
                else:
                    plan._skip(f"{rel} (special file, not copied)")
            except OSError as exc:
                plan._skip(f"{rel} (unreadable: {exc.strerror or exc})")


def _outer_repo_warning(src: Path) -> list[str]:
    if (src / ".git").exists():
        return []
    for parent in list(src.parents)[:12]:
        if (parent / ".git").is_dir():
            return [
                f"The selected folder is inside the git repository '{parent}', but is not its root: "
                "git checks (tracked / ignored / uncommitted files) are skipped. Select the repository root "
                "to include them."
            ]
    return []


def snapshot_from_zip(data: bytes, dest: Path, name: str) -> Snapshot:
    """Extract a zip archive safely into ``dest`` (validated entirely before anything is written)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"This file is not a valid zip archive ({exc}).") from None
    with zf:
        infos = zf.infolist()
        if len(infos) > ZIP_MAX_MEMBERS:
            raise ValueError(f"The archive has too many entries ({len(infos)}, limit {ZIP_MAX_MEMBERS}).")
        plan = _Plan()
        for info in infos:
            _plan_zip_member(plan, zf, info)
        dest_root = _prepare_dest(dest)
        try:
            return _finish(plan, dest_root, kind="zip", source=None, name=name or "project")
        except (zipfile.BadZipFile, EOFError, RuntimeError, NotImplementedError) as exc:
            raise ValueError(f"The zip archive is corrupted or unsupported ({exc}).") from None


def _plan_zip_member(plan: _Plan, zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> None:
    rel = clean_member_path(info.filename)       # raises on absolute / drive / '..'
    if not rel:
        return
    for part in rel.split("/"):
        problem = windows_name_problem(part)
        if problem:
            plan._skip(f"{rel} ({problem}, not extracted)")
            return
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK or (info.external_attr & 0x400):   # unix symlink / windows reparse point
        plan._skip(f"{rel} (symbolic link, not extracted)")
        return
    if info.is_dir():
        plan.add_dir(rel)
        return
    if mode not in (0, stat.S_IFREG):
        plan._skip(f"{rel} (special file, not extracted)")
        return
    if info.flag_bits & 0x1:
        plan._skip(f"{rel} (encrypted, not extracted)")
        plan.warnings.append("Some files of the archive are password-protected: they were not extracted.")
        return
    if info.file_size > ZIP_RATIO_MIN_SIZE and info.file_size > ZIP_MAX_RATIO * max(info.compress_size, 1):
        raise ValueError(
            f"Suspicious compression ratio for '{rel}' ({info.file_size} bytes from {info.compress_size}): "
            "the archive looks like a zip bomb and was rejected."
        )
    if info.file_size > MAX_TOTAL_BYTES and plan.classify(rel, is_dir=False) == "keep":
        raise ValueError(
            f"'{rel}' declares {info.file_size / MB:.0f} MB once extracted (limit {MAX_TOTAL_BYTES // MB} MB in total): "
            "the archive was rejected."
        )

    def _open(info: zipfile.ZipInfo = info) -> BinaryIO:
        return _BoundedReader(zf.open(info), info.file_size, rel)

    plan.add_file(rel, info.file_size, _open)


class _BoundedReader(io.RawIOBase):
    """Reader that fails if a member decompresses to more bytes than its header declares."""

    def __init__(self, raw: BinaryIO, declared: int, rel: str) -> None:
        super().__init__()
        self._raw = raw
        self._left = declared
        self._rel = rel

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        chunk = self._raw.read(size if size and size > 0 else _CHUNK)
        if len(chunk) > self._left:
            raise ValueError(f"'{self._rel}' is larger than declared in the archive: the archive was rejected.")
        self._left -= len(chunk)
        return chunk

    def close(self) -> None:
        try:
            self._raw.close()
        finally:
            super().close()


def snapshot_from_upload(files: list[tuple[str, bytes]], dest: Path, name: str) -> Snapshot:
    """Write a browser folder upload (relative paths from ``webkitdirectory``) into ``dest``."""
    plan = _Plan()
    for raw, data in files:
        rel = clean_member_path(raw)              # raises on absolute / drive / '..'
        if not rel:
            raise ValueError(f"Invalid file path in the upload: {raw!r}")
        problem = next((p for p in (windows_name_problem(c) for c in rel.split("/")) if p), None)
        if problem:
            plan._skip(f"{rel} ({problem}, not saved)")
            continue
        payload = bytes(data)
        plan.add_file(rel, len(payload), lambda payload=payload: io.BytesIO(payload))
    dest_root = _prepare_dest(dest)
    return _finish(plan, dest_root, kind="upload", source=None, name=name or "uploaded-project")


# ---------------------------------------------------------------------------------------------
# .git neutralization
# ---------------------------------------------------------------------------------------------

_SECTION_RE = re.compile(r'^\[\s*([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\](.*)$')
_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*(?:=\s*(.*))?$")
_REMOTE_NAME_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_SAFE_CORE = {
    "autocrlf": {"true", "false", "input"},
    "eol": {"lf", "crlf", "native"},
}
_GIT_SEARCH_SKIP = SKIP_DIRS | {"__pycache__"}


def sanitize_git_dir(root: Path) -> None:
    """Neutralize every git repository found in a snapshot.

    For each git directory (``root/.git`` and nested ones, including ``.git/modules/*`` submodule dirs):
    ``config`` is rewritten to a minimal safe config (core.repositoryformatversion, bare = false, safe
    line-ending settings, needed extensions, remote urls), ``config.worktree``, ``commondir`` and object
    alternates are removed, and every hook is deleted. Git link files (``.git`` as a file) are removed.
    """
    root = Path(root)
    for git_path in _find_git_entries(root):
        if git_path.is_dir() and not git_path.is_symlink():
            _sanitize_git_tree(git_path)
        else:
            _unlink(git_path)


def _find_git_entries(root: Path, max_depth: int = 6) -> list[Path]:
    found: list[Path] = []
    if root.name == ".git":
        return [root]
    frontier = [root]
    for _ in range(max_depth + 1):
        nxt: list[Path] = []
        for d in frontier:
            try:
                entries = sorted(os.scandir(d), key=lambda e: e.name)
            except OSError:
                continue
            for e in entries:
                if e.name == ".git":
                    found.append(Path(e.path))
                    continue
                if e.name in _GIT_SEARCH_SKIP or is_link_like(e):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        nxt.append(Path(e.path))
                except OSError:
                    continue
        frontier = nxt
    return found


def _sanitize_git_tree(git_dir: Path) -> None:
    """Sanitize ``git_dir`` and every git directory below it (submodules, worktrees)."""
    for dirpath, dirnames, filenames in os.walk(git_dir, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink()]
        if "HEAD" in filenames and ("config" in filenames or "objects" in dirnames or "commondir" in filenames):
            _sanitize_one_gitdir(here)          # clears <gitdir>/hooks (not refs named "hooks/...")
            dirnames[:] = [d for d in dirnames if d != "hooks"]


def _sanitize_one_gitdir(gitdir: Path) -> None:
    config = gitdir / "config"
    text = ""
    if config.is_file() and not config.is_symlink():
        try:
            text = config.read_bytes()[: 1 * MB].decode("utf-8", errors="replace")
        except OSError:
            text = ""
    new_text = _safe_config(text)
    _unlink(config)
    try:
        config.write_text(new_text, encoding="utf-8", newline="\n")
    except OSError:
        pass
    for name in ("config.worktree", "commondir", "objects/info/alternates", "objects/info/http-alternates"):
        target = gitdir / name
        if target.exists() or target.is_symlink():
            _unlink(target)
    hooks = gitdir / "hooks"
    if hooks.is_symlink():
        _unlink(hooks)
    if hooks.is_dir():
        _clear_dir(hooks)


def _clear_dir(path: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        for f in filenames:
            _unlink(Path(dirpath) / f)
        for d in dirnames:
            p = Path(dirpath) / d
            try:
                if p.is_symlink():
                    _unlink(p)
                else:
                    os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                    p.rmdir()
            except OSError:
                pass


def _parse_git_config(text: str) -> list[tuple[str, str | None, str, str]]:
    """Very small git-config reader: ``(section, subsection, key, value)`` (section/key lowercased).

    Only used to *extract* a few whitelisted values from an untrusted config, never to execute it.
    """
    out: list[tuple[str, str | None, str, str]] = []
    section, sub = "", None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        while line.endswith("\\") and i < len(lines):
            line = line[:-1] + lines[i].strip()
            i += 1
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            m = _SECTION_RE.match(line)
            if not m:
                section, sub = "", None
                continue
            name, quoted, rest = m.group(1), m.group(2), m.group(3).strip()
            if quoted is not None:
                section, sub = name.lower(), re.sub(r"\\(.)", r"\1", quoted)
            elif "." in name:
                head, _, tail = name.partition(".")
                section, sub = head.lower(), tail.lower()
            else:
                section, sub = name.lower(), None
            if not rest or rest[0] in "#;":
                continue
            line = rest
        m = _KEY_RE.match(line)
        if not m or not section:
            continue
        out.append((section, sub, m.group(1).lower(), _config_value(m.group(2))))
    return out


def _config_value(raw: str | None) -> str:
    if raw is None:
        return "true"
    out: list[str] = []
    quoted = False
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            out.append({"n": "\n", "t": "\t", "b": "\b"}.get(nxt, nxt))
            i += 2
            continue
        if ch == '"':
            quoted = not quoted
        elif ch in "#;" and not quoted:
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).strip()


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _safe_config(text: str) -> str:
    version = 0
    extensions: dict[str, str] = {}
    core: dict[str, str] = {}
    remotes: dict[str, str] = {}
    for section, sub, key, value in _parse_git_config(text):
        if section == "core" and sub is None:
            if key == "repositoryformatversion" and value.strip() in ("0", "1"):
                version = int(value.strip())
            elif key in _SAFE_CORE and value.lower() in _SAFE_CORE[key]:
                core[key] = value.lower()
        elif section == "extensions" and sub is None:
            if key == "objectformat" and value.lower() in ("sha1", "sha256"):
                extensions[key] = value.lower()
            elif key == "refstorage" and value.lower() in ("files", "reftable"):
                extensions[key] = value.lower()
        elif section == "remote" and sub and key == "url":
            if (_REMOTE_NAME_RE.match(sub) and sub not in remotes and len(value) <= 2048
                    and not any(ord(c) < 32 or ord(c) == 127 for c in value)):
                remotes[sub] = value
    lines = ["[core]", f"\trepositoryformatversion = {version}", "\tbare = false", "\tfilemode = false"]
    lines += [f"\t{k} = {v}" for k, v in sorted(core.items())]
    if version == 1 and extensions:
        lines.append("[extensions]")
        lines += [f"\t{k} = {v}" for k, v in sorted(extensions.items())]
    for name, url in remotes.items():
        lines.append(f"[remote {_quote(name)}]")
        lines.append(f"\turl = {_quote(url)}")
    return "\n".join(lines) + "\n"
