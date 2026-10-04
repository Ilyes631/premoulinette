"""Find the student's git repositories on this computer, so they can click one instead of typing a path.

Security: the repositories are untrusted, so NOTHING is executed inside them (no ``git``). Only three
small text files are read as plain data, with size caps: ``.git/HEAD``, the last 4 KB of
``.git/logs/HEAD`` and ``.git/config``. Credentials are stripped from every URL. Symlinks and junctions
are never followed, a global time budget bounds the scan, and the result is cached for 60 s.

Scanned roots:
* Windows: the user's usual folders (Desktop, Documents, Downloads, OneDrive…, top level of the profile)
  and, for every WSL distribution (default first), ``/root`` and ``/home/<user>`` through
  ``\\\\wsl.localhost\\<distro>``;
* Linux / macOS: the home folder (top level) and its usual sub-folders.
"""
from __future__ import annotations

import codecs
import copy
import os
import posixpath
import re
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

MAX_DEPTH = 4
MAX_PROJECTS = 50
MAX_FOUND = 500
TIME_BUDGET_S = 8.0
CACHE_TTL_S = 60.0
WSL_TIMEOUT_S = 5.0
LOG_TAIL_BYTES = 4096
SMALL_FILE_MAX = 64 * 1024
MESSAGE_MAX = 200
WORKERS = 6
MAX_HOMES = 20
UNC_PREFIXES: tuple[str, ...] = ("\\\\wsl.localhost\\", "\\\\wsl$\\")

# Directory names never descended into (compared lowercased). Every hidden directory (".xxx") is
# skipped too: .venv, .cache, .git, .npm, .local (.local/share), .oh-my-zsh, .nvm…
SKIP_DIRS = frozenset({
    "node_modules", "venv", "env", "appdata", "__pycache__", "site-packages", "snap", "afs",
    "$recycle.bin", "system volume information",
})
WINDOWS_FOLDERS = (
    "Desktop", "Bureau", "Documents", "Downloads", "source\\repos", "Projects", "Projets", "dev", "code",
    "repos", "git", "GitHub", "epita",
)
ONEDRIVE_FOLDERS = ("Bureau", "Documents", "Desktop")
POSIX_FOLDERS = (
    "Desktop", "Bureau", "Documents", "Downloads", "Projects", "projects", "Projets", "dev", "src", "code",
    "repos", "git", "work", "epita",
)

_DISTRO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")   # no spaces, slashes or ".."
_CREDENTIALS_RE = re.compile(r"(?<=://)[^/@\s]+@")
_SCP_HOST_RE = re.compile(r"^(?:[^@/\s]+@)?([^:/\s]+):")
_TZ_RE = re.compile(r"^[+-]\d{4}$")
_SECTION_RE = re.compile(r'^\s*\[\s*([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\]')
_URL_KEY_RE = re.compile(r"^\s*url\s*=\s*(.*?)\s*$", re.IGNORECASE)


# ---- data ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanRoot:
    path: str                       # OS path that is scanned
    label: str                      # human label ("Ubuntu: /root", "C:\\Users\\x\\Desktop")
    location: str                   # "wsl" | "windows" | "posix"
    distro: str | None = None
    linux_path: str | None = None   # Linux path of ``path`` for WSL roots ("/root")
    unc_base: str | None = None     # "\\\\wsl.localhost\\Ubuntu" for WSL roots
    max_depth: int = MAX_DEPTH


@dataclass
class DiscoveredProject:
    path: str
    name: str
    location: str
    distro: str | None
    display_path: str
    branch: str | None
    last_activity: str | None
    last_message: str | None
    remote_url: str | None
    is_school: bool
    timestamp: float | None = None   # sort key only (not serialized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path, "name": self.name, "location": self.location, "distro": self.distro,
            "display_path": self.display_path, "branch": self.branch, "last_activity": self.last_activity,
            "last_message": self.last_message, "remote_url": self.remote_url, "is_school": self.is_school,
        }


# ---- pure helpers (unit-tested) ------------------------------------------------------------------------


def strip_credentials(text: str | None) -> str | None:
    """``https://user:token@host/x`` -> ``https://host/x`` (anywhere in ``text``)."""
    if not text:
        return text
    return _CREDENTIALS_RE.sub("", text)


def remote_host(url: str | None) -> str:
    """Host of a git remote url (``https://host/…``, ``ssh://git@host:22/…`` or scp-like ``git@host:…``)."""
    if not url:
        return ""
    if "://" in url:
        netloc = url.split("://", 1)[1].split("/", 1)[0].rsplit("@", 1)[-1]
        host = netloc[1:].split("]", 1)[0] if netloc.startswith("[") else netloc.split(":", 1)[0]
        return host.lower()
    m = _SCP_HOST_RE.match(url)
    return m.group(1).lower() if m else ""


def is_school_project(name: str, remote_url: str | None) -> bool:
    return name.lower().startswith("epita-") or "epita" in remote_host(remote_url)


def parse_head(text: str | None) -> str | None:
    """Branch name from the content of ``.git/HEAD`` (None when detached / unreadable)."""
    if not text:
        return None
    line = text.strip().splitlines()[0] if text.strip() else ""
    if not line.startswith("ref:"):
        return None
    ref = line[4:].strip()
    return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else (ref or None)


def parse_reflog_tail(text: str | None) -> tuple[int, str] | None:
    """(unix timestamp, message) of the last valid entry of ``.git/logs/HEAD``.

    Entry format: ``<old> <new> <name> <email> <unix-ts> <tz>\\t<message>``.
    """
    if not text:
        return None
    for line in reversed(text.splitlines()):
        if not line.strip():
            continue
        meta, _, message = line.partition("\t")
        parts = meta.rsplit(" ", 2)
        if len(parts) != 3 or not _TZ_RE.match(parts[2]):
            return None
        try:
            ts = int(parts[1])
        except ValueError:
            return None
        return ts, message.strip()
    return None


def parse_remote_url(text: str | None) -> str | None:
    """``url`` of ``[remote "origin"]`` in a git config file (else the first remote's url)."""
    if not text:
        return None
    section: tuple[str, str | None] | None = None
    urls: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        m = _SECTION_RE.match(line)
        if m:
            section = (m.group(1).lower(), m.group(2))
            continue
        if section is None or section[0] != "remote" or section[1] is None:
            continue
        k = _URL_KEY_RE.match(line)
        if k:
            value = k.group(1)
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            urls.setdefault(section[1], value)
    url = urls.get("origin") or next(iter(urls.values()), None)
    return url or None


def sort_projects(projects: Iterable[DiscoveredProject]) -> list[DiscoveredProject]:
    """School projects first, then the most recent activity first (unknown activity last)."""
    return sorted(
        projects,
        key=lambda p: (not p.is_school, p.timestamp is None, -(p.timestamp or 0.0), p.name.lower()),
    )


def decode_wsl_output(raw: bytes) -> str:
    """``wsl.exe`` prints UTF-16-LE (with BOM / NULs) unless ``WSL_UTF8=1``: decode either robustly."""
    if raw.startswith(codecs.BOM_UTF16_LE) or b"\x00" in raw:
        text = raw.decode("utf-16-le", "replace")
    else:
        text = raw.decode("utf-8", "replace")
    return text.replace("\ufeff", "").replace("\x00", "")


def _valid_distro(name: str) -> bool:
    return bool(_DISTRO_RE.match(name)) and not name.lower().startswith("docker-desktop")


def parse_wsl_list_quiet(raw: bytes) -> list[str]:
    """Distribution names from ``wsl.exe -l -q``."""
    names: list[str] = []
    for line in decode_wsl_output(raw).splitlines():
        name = line.strip()
        if _valid_distro(name) and name not in names:
            names.append(name)
    return names


def parse_wsl_list_verbose(raw: bytes) -> tuple[list[str], str | None]:
    """(names, default) from ``wsl.exe -l -v`` (the default is marked with ``*``; header localized)."""
    names: list[str] = []
    default: str | None = None
    lines = [ln for ln in decode_wsl_output(raw).splitlines() if ln.strip()]
    for line in lines[1:]:   # first line = header ("NAME STATE VERSION", localized)
        s = line.strip()
        is_default = s.startswith("*")
        tokens = s.lstrip("*").split()
        if not tokens or not _valid_distro(tokens[0]):
            continue
        if tokens[0] not in names:
            names.append(tokens[0])
        if is_default:
            default = tokens[0]
    return names, default


def order_distros(names: Iterable[str], default: str | None) -> list[str]:
    """Valid, non-Docker distributions, default first, without duplicates."""
    out: list[str] = []
    for name in ([default] if default else []) + list(names):
        if name and _valid_distro(name) and name not in out:
            out.append(name)
    return out


def linux_path_to_wsl(raw: str, distros: Sequence[str],
                      is_dir: Callable[[str], bool] = os.path.isdir) -> str | None:
    """``/root/tp`` -> ``\\\\wsl.localhost\\<distro>\\root\\tp`` for the first distro where it is a folder."""
    if not raw.startswith("/") or raw.startswith("//") or "\x00" in raw:
        return None
    parts = [p for p in posixpath.normpath(raw).split("/") if p and p != ".."]
    for distro in distros:
        if not _valid_distro(distro):
            continue
        for prefix in UNC_PREFIXES:
            candidate = os.path.join(prefix + distro, *parts) if parts else prefix + distro
            try:
                if is_dir(candidate):
                    return candidate
            except (OSError, ValueError):
                continue
    return None


# ---- WSL distributions -----------------------------------------------------------------------------------

_DISTRO_CACHE: tuple[float, list[str]] | None = None
_DISTRO_LOCK = threading.Lock()


def _registry_distros() -> tuple[list[str], str | None]:
    try:
        import winreg
    except ImportError:
        return [], None
    names: list[str] = []
    default: str | None = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Lxss") as key:
            try:
                default_guid = str(winreg.QueryValueEx(key, "DefaultDistribution")[0]).lower()
            except OSError:
                default_guid = ""
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(key, sub) as k:
                        name = winreg.QueryValueEx(k, "DistributionName")[0]
                except OSError:
                    continue
                if isinstance(name, str):
                    names.append(name)
                    if sub.lower() == default_guid:
                        default = name
    except OSError:
        return [], None
    return names, default


def _run_wsl(*args: str) -> bytes | None:
    try:
        proc = subprocess.run(
            ["wsl.exe", *args], capture_output=True, stdin=subprocess.DEVNULL, timeout=WSL_TIMEOUT_S,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _detect_distros() -> list[str]:
    names, default = _registry_distros()
    if names:
        return order_distros(names, default)
    raw = _run_wsl("-l", "-q")
    names = parse_wsl_list_quiet(raw) if raw else []
    if not names:
        return []
    verbose = _run_wsl("-l", "-v")
    _, default = parse_wsl_list_verbose(verbose) if verbose else ([], None)
    return order_distros(names, default)


def list_wsl_distros() -> list[str]:
    """Installed WSL distributions (default first, Docker's excluded). Empty outside Windows. Cached 60 s."""
    global _DISTRO_CACHE
    if os.name != "nt":
        return []
    with _DISTRO_LOCK:
        now = time.monotonic()
        if _DISTRO_CACHE is None or now - _DISTRO_CACHE[0] > CACHE_TTL_S:
            _DISTRO_CACHE = (now, _detect_distros())
        return list(_DISTRO_CACHE[1])


# ---- roots -----------------------------------------------------------------------------------------------


def _norm(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def windows_roots(home: Path | None = None) -> list[ScanRoot]:
    home = home or Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [home / name for name in WINDOWS_FOLDERS]
    try:
        with os.scandir(home) as it:
            onedrives = sorted(e.name for e in it if e.name.lower().startswith("onedrive")
                               and e.is_dir(follow_symlinks=False))
    except OSError:
        onedrives = []
    candidates += [home / od / sub for od in onedrives for sub in ONEDRIVE_FOLDERS]
    roots = [ScanRoot(str(home), f"{home} (top level)", "windows", max_depth=1)]
    seen = {_norm(home)}
    for path in candidates:
        if _norm(path) not in seen and path.is_dir():
            seen.add(_norm(path))
            roots.append(ScanRoot(str(path), str(path), "windows"))
    return roots


def posix_roots(home: Path | None = None) -> list[ScanRoot]:
    home = home or Path.home()
    roots = [ScanRoot(str(home), "~ (top level)", "posix", max_depth=1)]
    for name in POSIX_FOLDERS:
        path = home / name
        if path.is_dir():
            roots.append(ScanRoot(str(path), f"~/{name}", "posix"))
    return roots


def wsl_distro_roots(distro: str) -> list[ScanRoot]:
    """``/root`` and every ``/home/<user>`` of a WSL distribution, as UNC paths."""
    for prefix in UNC_PREFIXES:
        base = prefix + distro
        if os.path.isdir(base + "\\root") or os.path.isdir(base + "\\home"):
            break
    else:
        return []
    roots = [ScanRoot(base + "\\root", f"{distro}: /root", "wsl", distro, "/root", base)]
    try:
        with os.scandir(base + "\\home") as it:
            homes = sorted(e.name for e in it if not e.name.startswith(".") and e.is_dir(follow_symlinks=False))
    except OSError:
        homes = []
    roots += [ScanRoot(f"{base}\\home\\{u}", f"{distro}: /home/{u}", "wsl", distro, f"/home/{u}", base)
              for u in homes[:MAX_HOMES]]
    return roots


RootsTask = Callable[[], list[ScanRoot]]


def default_tasks() -> list[RootsTask]:
    """One task per WSL distribution (slow: scanned first) and one per local root."""
    if os.name == "nt":
        tasks: list[RootsTask] = [partial(wsl_distro_roots, d) for d in list_wsl_distros()]
        tasks += [partial(lambda r: [r], r) for r in windows_roots()]
        return tasks
    return [partial(lambda r: [r], r) for r in posix_roots()]


# ---- reading one repository (plain files only, never git) -----------------------------------------------


def _read_small(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            data = fh.read(SMALL_FILE_MAX + 1)
    except (OSError, ValueError):
        return None
    if len(data) > SMALL_FILE_MAX:
        return None
    return data.decode("utf-8", "replace")


def _read_tail(path: str, size: int = LOG_TAIL_BYTES) -> str | None:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            fh.seek(max(0, end - size))
            data = fh.read(size)
    except (OSError, ValueError):
        return None
    return data.decode("utf-8", "replace")


def _git_dirs(repo: str, root: ScanRoot) -> tuple[str, str] | None:
    """(git dir, common dir) of ``repo``; handles the ``.git`` file of a worktree."""
    dot_git = os.path.join(repo, ".git")
    if os.path.isdir(dot_git):
        return dot_git, dot_git
    text = _read_small(dot_git)
    if not text or not text.startswith("gitdir:"):
        return None
    target = text[len("gitdir:"):].strip().splitlines()[0] if text[len("gitdir:"):].strip() else ""
    if not target:
        return None
    if target.startswith("/") and root.unc_base:
        git_dir = os.path.join(root.unc_base, *[p for p in target.split("/") if p and p != ".."])
    else:
        git_dir = os.path.normpath(os.path.join(repo, target))
    common = _read_small(os.path.join(git_dir, "commondir"))
    common_dir = os.path.normpath(os.path.join(git_dir, common.strip())) if common and common.strip() else git_dir
    return git_dir, common_dir


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def read_project(repo: str, root: ScanRoot, rel: Sequence[str]) -> DiscoveredProject:
    name = rel[-1] if rel else (os.path.basename(repo.rstrip("\\/")) or repo)
    branch = message = remote = None
    ts: float | None = None
    dirs = _git_dirs(repo, root)
    if dirs is not None:
        git_dir, common_dir = dirs
        branch = parse_head(_read_small(os.path.join(git_dir, "HEAD")))
        entry = parse_reflog_tail(_read_tail(os.path.join(git_dir, "logs", "HEAD")))
        if entry is not None:
            ts, message = float(entry[0]), strip_credentials(entry[1])[:MESSAGE_MAX] or None
        else:
            try:
                ts = os.stat(os.path.join(git_dir, "index")).st_mtime
            except OSError:
                ts = None
        remote = strip_credentials(parse_remote_url(_read_small(os.path.join(common_dir, "config"))))
    if root.location == "wsl":
        display = f"{root.distro}: {posixpath.join(root.linux_path or '/', *rel)}"
    else:
        display = repo
    return DiscoveredProject(
        path=repo, name=name, location=root.location, distro=root.distro, display_path=display,
        branch=branch, last_activity=_iso(ts) if ts is not None else None, last_message=message,
        remote_url=remote, is_school=is_school_project(name, remote), timestamp=ts,
    )


# ---- scanning ----------------------------------------------------------------------------------------------


class _Scan:
    def __init__(self, deadline: float, exclude: Sequence[str | Path]) -> None:
        self.deadline = deadline
        self.exclude = [_norm(p) for p in exclude]
        self.lock = threading.Lock()
        self.found: dict[str, DiscoveredProject] = {}
        self.scanned: list[str] = []

    def expired(self) -> bool:
        return time.monotonic() > self.deadline

    def excluded(self, path: str) -> bool:
        p = _norm(path)
        return any(p == e or p.startswith(e.rstrip("\\/") + os.sep) for e in self.exclude)

    def add(self, project: DiscoveredProject) -> None:
        with self.lock:
            if len(self.found) < MAX_FOUND:
                self.found.setdefault(_norm(project.path), project)

    def mark_scanned(self, label: str) -> None:
        with self.lock:
            if label not in self.scanned:
                self.scanned.append(label)


def _skip_entry(entry: os.DirEntry[str]) -> bool:
    name = entry.name
    if name.startswith(".") or name.lower() in SKIP_DIRS:
        return True
    try:
        if entry.is_symlink() or getattr(entry, "is_junction", lambda: False)():
            return True
        return not entry.is_dir(follow_symlinks=False)
    except OSError:
        return True


def scan_root(root: ScanRoot, scan: _Scan) -> None:
    """Breadth-first walk of ``root`` (depth-limited, links never followed, errors skipped)."""
    if scan.excluded(root.path):
        return
    queue: deque[tuple[str, int, tuple[str, ...]]] = deque([(root.path, 0, ())])
    while queue:
        if scan.expired():
            return
        path, depth, rel = queue.popleft()
        try:
            with os.scandir(path) as it:
                entries = list(it)
        except (OSError, ValueError):
            continue
        if depth == 0:
            scan.mark_scanned(root.label)
        if any(e.name == ".git" for e in entries):
            try:
                scan.add(read_project(path, root, rel))
            except Exception:   # noqa: BLE001 - one odd repository must not break the scan
                pass
            if depth > 0:
                continue   # never descend into a repository
        if depth >= root.max_depth:
            continue
        for entry in sorted(entries, key=lambda e: e.name.lower()):
            if _skip_entry(entry):
                continue
            child = os.path.join(path, entry.name)
            if not scan.excluded(child):
                queue.append((child, depth + 1, rel + (entry.name,)))


def _worker(tasks: deque[RootsTask], scan: _Scan) -> None:
    while not scan.expired():
        try:
            task = tasks.popleft()
        except IndexError:
            return
        try:
            roots = task()
        except Exception:   # noqa: BLE001
            continue
        for root in roots:
            if scan.expired():
                return
            scan_root(root, scan)


def scan(tasks: Sequence[RootsTask], exclude: Sequence[str | Path] = (),
         budget_s: float = TIME_BUDGET_S) -> dict[str, Any]:
    """Run ``tasks`` on a few daemon threads; returns after all of them or when the budget is spent."""
    started = time.monotonic()
    state = _Scan(started + budget_s, exclude)
    queue: deque[RootsTask] = deque(tasks)
    threads = [threading.Thread(target=_worker, args=(queue, state), daemon=True, name=f"pm-discover-{i}")
               for i in range(min(WORKERS, len(tasks)))]
    for t in threads:
        t.start()
    for t in threads:   # a blocked network read cannot hold the request: daemon threads are abandoned
        t.join(timeout=max(0.0, state.deadline - time.monotonic()) + 0.2)
    with state.lock:
        projects = sort_projects(state.found.values())[:MAX_PROJECTS]
        scanned = list(state.scanned)
    return {
        "projects": [p.to_dict() for p in projects],
        "scanned": scanned,
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
    }


_CACHE: tuple[tuple[str, ...], float, dict[str, Any]] | None = None
_CACHE_LOCK = threading.Lock()


def clear_cache() -> None:
    global _CACHE, _DISTRO_CACHE
    with _CACHE_LOCK:
        _CACHE = None
    with _DISTRO_LOCK:
        _DISTRO_CACHE = None


def discover_projects(*, refresh: bool = False, exclude: Sequence[str | Path] = ()) -> dict[str, Any]:
    """``GET /api/projects/discover`` payload: ``{projects, scanned, duration_ms}`` (cached 60 s)."""
    global _CACHE
    key = tuple(_norm(p) for p in exclude)
    with _CACHE_LOCK:   # concurrent requests wait for the running scan instead of starting another
        if not refresh and _CACHE is not None and _CACHE[0] == key and time.monotonic() - _CACHE[1] < CACHE_TTL_S:
            return copy.deepcopy(_CACHE[2])
        result = scan(default_tasks(), exclude)
        _CACHE = (key, time.monotonic(), result)
        return copy.deepcopy(result)
