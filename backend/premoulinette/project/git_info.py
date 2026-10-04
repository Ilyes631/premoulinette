"""Read-only git inspection of a (sanitized) snapshot repository.

Every git command runs hardened:

* ``--git-dir``/``--work-tree`` explicit and ``GIT_CEILING_DIRECTORIES`` set: git never discovers a
  repository above the snapshot (snapshots live inside PréMoulinette's data dir, maybe in a checkout);
* ``-c core.fsmonitor=false -c core.hooksPath=<empty temp dir> -c protocol.allow=never -c core.pager=cat``
  (+ no untracked cache, no signatures, no colors), ``--no-optional-locks``;
* environment: every inherited ``GIT_*`` variable dropped, ``GIT_CONFIG_NOSYSTEM=1``, ``GIT_CONFIG_GLOBAL``
  = an empty file, ``GIT_TERMINAL_PROMPT=0``, ``GIT_OPTIONAL_LOCKS=0``;
* stdin closed, per-command timeout, overall deadline.

Only read commands are used (rev-parse, status, log, check-ignore, config --get, tag --list).
Nothing is ever fetched, pushed, committed or tagged.

Line endings: the user's own ``core.autocrlf`` / ``core.eol`` (global/system config, trusted) are
re-applied unless the repository sets them, otherwise every CRLF file checked out on Windows would be
reported as modified. Case: ``core.ignorecase=false`` so tracking is compared with the exact case, like
on the Linux grader (a file renamed ``Kelvin.py`` -> ``kelvin.py`` without ``git mv`` shows as untracked).
"""
from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from premoulinette.results.models import GitInfo

COMMAND_TIMEOUT_S = 10.0
TOTAL_TIMEOUT_S = 25.0
MAX_TAGS = 50
_SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache"})
_CREDENTIALS_RE = re.compile(r"(?<=://)[^/@\s]*@")
_INHERITED_SETTINGS = ("core.autocrlf", "core.eol")
_SAFE_VALUES = {"core.autocrlf": {"true", "false", "input"}, "core.eol": {"lf", "crlf", "native"}}


class _GitError(Exception):
    pass


def git_executable() -> str | None:
    return shutil.which("git")


def _base_env(ceiling: Path | None, global_config: Path | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "LANGUAGE": "C",
    })
    env.pop("PAGER", None)
    if global_config is not None:
        env["GIT_CONFIG_GLOBAL"] = str(global_config)
    if ceiling is not None:
        env["GIT_CEILING_DIRECTORIES"] = str(ceiling)
    return env


def _creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


@functools.lru_cache(maxsize=1)
def _user_line_ending_settings() -> dict[str, str]:
    """``core.autocrlf`` / ``core.eol`` from the user's own (trusted) global and system config."""
    git = git_executable()
    if git is None:
        return {}
    out: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="pm-gitcfg-") as tmp:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CEILING_DIRECTORIES": str(Path(tmp).parent)})
        for key in _INHERITED_SETTINGS:
            try:
                proc = subprocess.run(
                    [git, "config", "--get", key], cwd=tmp, env=env, capture_output=True,
                    stdin=subprocess.DEVNULL, timeout=5, creationflags=_creationflags(),
                )
            except (OSError, subprocess.SubprocessError):
                continue
            value = proc.stdout.decode("utf-8", "replace").strip().lower()
            if proc.returncode == 0 and value in _SAFE_VALUES[key]:
                out[key] = value
    return out


class _Git:
    def __init__(self, git: str, repo_root: Path, tmp: Path) -> None:
        self.repo_root = repo_root
        self.deadline = time.monotonic() + TOTAL_TIMEOUT_S
        hooks = tmp / "hooks"
        hooks.mkdir()
        global_config = tmp / "empty-global.gitconfig"
        global_config.write_bytes(b"")
        self.env = _base_env(repo_root.parent, global_config)
        self.base = [
            git, "--no-pager", "--no-optional-locks",
            f"--git-dir={repo_root / '.git'}", f"--work-tree={repo_root}",
            "-c", "core.fsmonitor=false",
            "-c", f"core.hooksPath={hooks}",
            "-c", "protocol.allow=never",
            "-c", "core.pager=cat",
            "-c", "core.untrackedCache=false",
            "-c", "core.filemode=false",
            "-c", "core.ignorecase=false",
            "-c", "core.quotepath=false",
            "-c", "core.splitIndex=false",
            "-c", "color.ui=false",
            "-c", "log.showSignature=false",
            "-c", "gc.auto=0",
            "-c", "maintenance.auto=false",
            "-c", f"safe.directory={repo_root.as_posix()}",
        ]

    def run(self, *args: str, ok_codes: tuple[int, ...] = (0,), input_bytes: bytes | None = None,
            extra_config: list[str] | None = None) -> bytes:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise _GitError("git took too long (overall timeout)")
        cmd = list(self.base)
        for item in extra_config or []:
            cmd += ["-c", item]
        cmd += list(args)
        try:
            proc = subprocess.run(
                cmd, cwd=self.repo_root, env=self.env, capture_output=True,
                input=input_bytes if input_bytes is not None else b"",
                timeout=min(COMMAND_TIMEOUT_S, remaining), creationflags=_creationflags(),
            )
        except subprocess.TimeoutExpired:
            raise _GitError(f"git {args[0]} timed out") from None
        except OSError as exc:
            raise _GitError(f"git could not be started: {exc}") from None
        if proc.returncode not in ok_codes:
            message = proc.stderr.decode("utf-8", "replace").strip().splitlines()
            raise _GitError(f"git {args[0]} failed: {message[-1] if message else f'exit code {proc.returncode}'}")
        return proc.stdout


def redact_url(url: str | None) -> str | None:
    """Remove credentials (``https://user:token@host``) from a remote url."""
    if not url:
        return None
    return _CREDENTIALS_RE.sub("", url)


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", "replace")


def _in_skipped_dir(path: str) -> bool:
    return any(part in _SKIP_DIRS for part in path.split("/")[:-1])


def parse_status_v2(raw: bytes) -> dict[str, object]:
    """Parse ``git status --porcelain=v2 -z --branch`` output."""
    records = raw.split(b"\x00")
    out: dict[str, object] = {"oid": None, "head": None, "modified": [], "untracked": [], "staged": []}
    modified: list[str] = out["modified"]  # type: ignore[assignment]
    untracked: list[str] = out["untracked"]  # type: ignore[assignment]
    staged: list[str] = out["staged"]  # type: ignore[assignment]
    i = 0
    while i < len(records):
        rec = _decode(records[i])
        i += 1
        if not rec:
            continue
        if rec.startswith("# "):
            parts = rec[2:].split(" ", 1)
            if len(parts) == 2 and parts[0] == "branch.oid":
                out["oid"] = None if parts[1] == "(initial)" else parts[1]
            elif len(parts) == 2 and parts[0] == "branch.head":
                out["head"] = None if parts[1] == "(detached)" else parts[1]
            continue
        kind = rec[0]
        if kind == "?":
            untracked.append(rec[2:])
            continue
        if kind == "!":
            continue
        if kind == "1":
            fields = rec.split(" ", 8)
        elif kind == "2":
            fields = rec.split(" ", 9)
            i += 1  # the original path follows as its own NUL-terminated record
        elif kind == "u":
            fields = rec.split(" ", 10)
        else:
            continue
        if len(fields) < 3:
            continue
        xy, path = fields[1], fields[-1]
        if kind == "u":
            modified.append(path)
            staged.append(path)
            continue
        if len(xy) == 2:
            if xy[0] != ".":
                staged.append(path)
            if xy[1] != ".":
                modified.append(path)
    return out


def read_git_info(repo_root: Path, required_paths: list[str]) -> GitInfo:
    """Git state of the repository whose work tree is ``repo_root`` (paths relative to it).

    ``required_paths`` (POSIX, relative to ``repo_root``) are tested with ``git check-ignore``:
    the ones that are ignored *and not tracked* end up in ``ignored_required``.
    Never raises: problems are reported in ``GitInfo.error``.
    """
    repo_root = Path(repo_root).resolve()
    git_dir = repo_root / ".git"
    if not git_dir.is_dir() or git_dir.is_symlink():
        return GitInfo(is_repo=False)
    git = git_executable()
    if git is None:
        return GitInfo(is_repo=True, error="Git is not installed (or not on PATH): git checks were skipped.")
    try:
        with tempfile.TemporaryDirectory(prefix="pm-git-") as tmp:
            return _read(_Git(git, repo_root, Path(tmp)), required_paths)
    except _GitError as exc:
        return GitInfo(is_repo=True, error=str(exc))
    except OSError as exc:  # pragma: no cover - temp dir problems
        return GitInfo(is_repo=True, error=f"Git information could not be read: {exc}")


def _line_ending_overrides(g: _Git) -> list[str]:
    overrides: list[str] = []
    user = _user_line_ending_settings()
    for key in _INHERITED_SETTINGS:
        if key not in user:
            continue
        repo_value = g.run("config", "--get", key, ok_codes=(0, 1)).strip()
        if not repo_value:
            overrides.append(f"{key}={user[key]}")
    return overrides


def _read(g: _Git, required_paths: list[str]) -> GitInfo:
    inside = _decode(g.run("rev-parse", "--is-inside-work-tree")).strip()
    if inside != "true":
        return GitInfo(is_repo=False, error="The .git folder is not a valid work tree repository.")
    overrides = _line_ending_overrides(g)
    status = parse_status_v2(g.run(
        "status", "--porcelain=v2", "-z", "--branch", "--untracked-files=all", "--ignore-submodules=all",
        "--no-renames", extra_config=overrides,
    ))
    modified = [p for p in status["modified"] if not _in_skipped_dir(p)]  # type: ignore[union-attr]
    untracked = [p for p in status["untracked"] if not _in_skipped_dir(p)]  # type: ignore[union-attr]
    staged = [p for p in status["staged"] if not _in_skipped_dir(p)]  # type: ignore[union-attr]
    info = GitInfo(
        is_repo=True, branch=status["head"],  # type: ignore[arg-type]
        modified=sorted(set(modified)), untracked=sorted(set(untracked)), staged=sorted(set(staged)),
    )
    info.dirty = bool(info.modified or info.untracked or info.staged)
    info.ignored_required = _ignored(g, required_paths)   # essential: an error here disables git checks
    # Informative only: failures do not invalidate the tracking information above.
    if status["oid"]:
        info.head = str(status["oid"])[:7]
        try:
            log = _decode(g.run("log", "-1", "--no-show-signature", "--format=%h%x00%s%x00%cI", "HEAD")).rstrip("\n")
            parts = log.split("\x00")
            if len(parts) == 3:
                info.head, info.last_commit_message, info.last_commit_date = parts[0], parts[1][:300], parts[2]
        except _GitError:
            pass
    try:
        info.remote_url = _remote_url(g)
        tags = _decode(g.run("tag", "--list")).splitlines()
        info.tags = sorted(t.strip() for t in tags if t.strip())[:MAX_TAGS]
    except _GitError:
        pass
    return info


def _ignored(g: _Git, required_paths: list[str]) -> list[str]:
    paths = []
    for p in required_paths:
        p = p.replace("\\", "/").strip("/")
        if (p and "\x00" not in p and "\n" not in p and not p.startswith(":")
                and ".." not in p.split("/") and p not in paths):
            paths.append(p)
    if not paths:
        return []
    raw = g.run("check-ignore", "-z", "--stdin", ok_codes=(0, 1),
                input_bytes=b"".join(p.encode("utf-8") + b"\x00" for p in paths))
    found = {_decode(x) for x in raw.split(b"\x00") if x}
    return [p for p in paths if p in found]


def _remote_url(g: _Git) -> str | None:
    raw = _decode(g.run("config", "-z", "--get-regexp", r"^remote\..*\.url$", ok_codes=(0, 1)))
    urls: dict[str, str] = {}
    for rec in raw.split("\x00"):
        if not rec:
            continue
        key, _, value = rec.partition("\n")
        name = key[len("remote."):-len(".url")] if key.startswith("remote.") and key.endswith(".url") else key
        urls.setdefault(name, value)
    url = urls.get("origin") or next(iter(urls.values()), None)
    return redact_url(url)
