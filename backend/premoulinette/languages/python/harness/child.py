"""PreMoulinette child runner: executes ONE job of a RunPlan in a fresh interpreter.

Usage (spawned by run_plan.py):  python -I -X utf8 child.py <job.json> <result.json>

STDLIB ONLY. Runs inside the sandbox, possibly on another Python version (3.11+, e.g. 3.12 in
Docker). It must never import ``premoulinette``.

What it does, in order:
  1. opens the result file (kept open: the guards installed later forbid writes outside the sandbox);
  2. replaces stdout/stderr with UTF-8, "\\n"-newline, unbuffered streams that record events and cap
     their size; stdin is read as UTF-8 with universal newlines;
  3. instruments ``print`` / ``input`` (events carry the innermost *student* frame file/line);
  4. installs an audit hook blocking network, process creation, native code and writes outside the
     allowed roots (each blocked event is recorded and raises PermissionError);
  5. starts a watchdog that reports a timeout with the student stack before the parent kills us;
  6. runs the job (function call / script / import) and writes a JobResult-shaped JSON document.
"""
from __future__ import annotations

import ast
import atexit
import builtins
import importlib.util
import io
import json
import linecache  # noqa: F401  (pre-imported: used by traceback formatting after guards are installed)
import os
import re
import sys
import threading
import time
import traceback
import types

MAX_REPR_CHARS = 10_000
MAX_MESSAGE_CHARS = 4_000
MAX_TRACEBACK_CHARS = 20_000
MAX_LITERAL_CHECK_CHARS = 100_000
MAX_BLOCKED = 50
DEFAULT_MAX_EVENTS = 5_000
DEFAULT_MAX_BYTES = 65_536
STUDENT_MODULE_PREFIX = "_premoulinette_student_"
SANDBOX_TAG = "[PreMoulinette sandbox]"

JOB_KINDS = ("function", "script", "import")

_REAL_EXIT = os._exit
_ORIGINAL_PRINT = builtins.print
_MISSING = object()


def _cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated, {len(text) - limit} more characters]"


def _safe_str(obj: object) -> str:
    try:
        return str(obj)
    except BaseException:  # noqa: BLE001 - student __str__ may raise anything
        try:
            return repr(obj)
        except BaseException:  # noqa: BLE001
            return f"<unprintable {type(obj).__name__} object>"


def _dir_prefix(path: str) -> str:
    return path if path.endswith(os.sep) else path + os.sep


_DEVNULLS = {os.path.normcase(os.path.realpath(os.devnull)), os.path.normcase(os.devnull), "\\\\.\\nul"}


# ---------------------------------------------------------------------------------------------
# Project paths: which frames belong to the student, where writes are allowed
# ---------------------------------------------------------------------------------------------


class _ProjectPaths:
    def __init__(self, project_root: str, write_roots: list[str]) -> None:
        self.root = os.path.abspath(project_root)
        self._root_prefix = _dir_prefix(os.path.normcase(self.root))
        self._rel_cache: dict[object, str | None] = {}
        self._write_roots: list[tuple[str, str]] = []
        for entry in write_roots:
            try:
                real = os.path.normcase(os.path.realpath(entry))
            except (OSError, ValueError):
                continue
            self._write_roots.append((real, _dir_prefix(real)))

    def rel(self, filename: object) -> str | None:
        """Project-relative POSIX path of a student source file, None for any other file."""
        cached = self._rel_cache.get(filename, _MISSING)
        if cached is not _MISSING:
            return cached  # type: ignore[return-value]
        rel = None
        if isinstance(filename, str) and filename and not filename.startswith("<"):
            absolute = os.path.abspath(filename)
            if os.path.normcase(absolute).startswith(self._root_prefix):
                rel = os.path.relpath(absolute, self.root).replace(os.sep, "/")
        self._rel_cache[filename] = rel
        return rel

    def is_writable(self, path: str) -> bool:
        try:
            real = os.path.normcase(os.path.realpath(path))
        except (OSError, ValueError):
            return False
        if real in _DEVNULLS:
            return True
        return any(real == root or real.startswith(prefix) for root, prefix in self._write_roots)


# ---------------------------------------------------------------------------------------------
# Recorder: I/O events, per-phase stdout, blocked operations, output caps
# ---------------------------------------------------------------------------------------------


class _Recorder:
    def __init__(self, paths: _ProjectPaths, max_events: int, max_bytes: int) -> None:
        self.paths = paths
        self.max_events = max_events
        self.max_bytes = max_bytes
        self.events: list[dict] = []
        self.phase = "import"  # "import" then "call" (function jobs); scripts only use "call"
        self.stdout_parts: dict[str, list[str]] = {"import": [], "call": []}
        self.stderr_parts: list[str] = []
        self.sizes = {"output": 0, "stderr": 0}
        self.blocked: list[str] = []
        self.limit_hit = False
        self.lock = threading.RLock()
        self.on_limit = None  # callable() -> NoReturn, set by the runner

    def locate(self, frame) -> tuple[str | None, int | None]:
        """File/line of the innermost frame that belongs to the student project."""
        rel_of = self.paths.rel
        while frame is not None:
            rel = rel_of(frame.f_code.co_filename)
            if rel is not None:
                return rel, frame.f_lineno
            frame = frame.f_back
        return None, None

    def event(self, kind: str, text: str, loc: tuple[str | None, int | None]) -> None:
        if len(self.events) < self.max_events:
            self.events.append({"kind": kind, "text": text, "file": loc[0], "line": loc[1]})

    def add_text(self, kind: str, text: str) -> None:
        if not text:
            return
        if kind == "stderr":
            self.stderr_parts.append(text)
        else:
            self.stdout_parts[self.phase].append(text)

    def block(self, name: str) -> None:
        if name not in self.blocked and len(self.blocked) < MAX_BLOCKED:
            self.blocked.append(name)

    def limit_reached(self) -> None:
        self.limit_hit = True
        if self.on_limit is not None:
            self.on_limit()


class _OutStream(io.TextIOWrapper):
    """stdout/stderr replacement: UTF-8, "\\n" newlines on every OS, unbuffered, recorded and capped."""

    def __init__(self, fd: int, kind: str, recorder: _Recorder, errors: str) -> None:
        super().__init__(
            io.open(fd, "wb", closefd=False), encoding="utf-8", errors=errors, newline="\n", write_through=True
        )
        self._pm_kind = kind
        self._pm_rec = recorder

    def write(self, s):  # type: ignore[override]
        if not isinstance(s, str):
            raise TypeError(f"write() argument must be str, not {type(s).__name__}")
        self._pm_emit(s, self._pm_rec.locate(sys._getframe(1)), record=True)
        return len(s)

    def _pm_emit(self, text: str, loc: tuple[str | None, int | None], *, record: bool) -> None:
        rec = self._pm_rec
        kind = self._pm_kind
        with rec.lock:
            if self.closed:
                raise ValueError("I/O operation on closed file.")
            data = text.encode("utf-8", self.errors)
            room = rec.max_bytes - rec.sizes[kind]
            overflow = len(data) > room
            if overflow:
                data = data[: max(room, 0)]
                text = data.decode("utf-8", "replace")
            if data:
                self.buffer.write(data)
                self.buffer.flush()
                rec.sizes[kind] += len(data)
            rec.add_text(kind, text)
            if record and text:
                rec.event(kind, text, loc)
            if overflow:
                rec.limit_reached()


def _make_print(rec: _Recorder):
    def print(*args, sep=" ", end="\n", file=None, flush=False):  # noqa: A001 - mirrors the builtin
        if file is None:
            file = sys.stdout
            if file is None:
                return None
        if sep is None:
            sep = " "
        elif not isinstance(sep, str):
            raise TypeError(f"sep must be None or a string, not {type(sep).__name__}")
        if end is None:
            end = "\n"
        elif not isinstance(end, str):
            raise TypeError(f"end must be None or a string, not {type(end).__name__}")
        if not isinstance(file, _OutStream):
            return _ORIGINAL_PRINT(*args, sep=sep, end=end, file=file, flush=flush)
        loc = rec.locate(sys._getframe(1))
        parts: list[str] = []
        try:
            for index, arg in enumerate(args):
                if index:
                    parts.append(sep)
                parts.append(str(arg))
            parts.append(end)
        finally:
            # like the builtin, what was produced before a failing __str__ is still written
            text = "".join(parts)
            if text:
                file._pm_emit(text, loc, record=True)
        if flush:
            file.flush()
        return None

    return print


def _make_input(rec: _Recorder):
    def input(*args):  # noqa: A001 - mirrors the builtin
        if len(args) > 1:
            raise TypeError(f"input expected at most 1 argument, got {len(args)}")
        loc = rec.locate(sys._getframe(1))
        out = sys.stdout
        if out is None:
            raise RuntimeError("input(): lost sys.stdout")
        if args:
            prompt = str(args[0])
            if prompt:
                if isinstance(out, _OutStream):
                    out._pm_emit(prompt, loc, record=True)
                else:
                    out.write(prompt)
        try:
            out.flush()
        except Exception:  # noqa: BLE001
            pass
        stdin = sys.stdin
        if stdin is None:
            raise RuntimeError("input(): lost sys.stdin")
        line = stdin.readline()
        if not line:
            raise EOFError("EOF when reading a line")
        if line.endswith("\n"):
            line = line[:-1]
        rec.event("input", line, loc)
        return line

    return input


# ---------------------------------------------------------------------------------------------
# Guards: audit hook
# ---------------------------------------------------------------------------------------------

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_WINAPI_WRITE_ACCESS = 0x40000000 | 0x10000000 | 0x0002 | 0x0004 | 0x00010000 | 0x00040000 | 0x00080000
_WINAPI_CREATING_DISPOSITIONS = {1, 2, 4, 5}
_IPV4_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
_IPV6_RE = re.compile(r"[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?:%\w+)?")

_NO_PROCESS = "process creation is disabled in the sandbox"
_NO_SIGNAL = "signalling other processes is disabled in the sandbox"
_NO_NETWORK = "network access is disabled in the sandbox"
_NO_NATIVE = "native code loading/calls are disabled in the sandbox"
_ALLOWED_NATIVE_LIBS = {"kernel32", "kernel32.dll"}


def _deny(reason: str):
    return lambda args: reason


def _disable_fork_exec(rec: _Recorder) -> None:
    """POSIX: ``_posixsubprocess.fork_exec`` raises no audit event of its own (``subprocess.Popen`` does,
    but student code could call the private primitive directly), so it is replaced before any student code
    runs — ``subprocess`` imported later binds to the replacement too."""
    try:
        import _posixsubprocess  # type: ignore[import-not-found]
    except ImportError:  # Windows: process creation goes through the audited _winapi.CreateProcess
        return

    def fork_exec(*_args, **_kwargs):
        rec.block("subprocess.Popen")
        raise PermissionError(f"{SANDBOX_TAG} subprocess.Popen: {_NO_PROCESS}")

    _posixsubprocess.fork_exec = fork_exec


def _is_numeric_host(host: str) -> bool:
    return bool(_IPV4_RE.fullmatch(host) or (":" in host and _IPV6_RE.fullmatch(host)))


class _Guard:
    """Audit hook: blocks dangerous operations, records them and raises PermissionError."""

    def __init__(self, paths: _ProjectPaths, rec: _Recorder) -> None:
        self._paths = paths
        self._rec = rec
        self._state = threading.local()
        first = self._path_args((0, None))
        handlers = {
            # process creation / signals
            "subprocess.Popen": _deny(_NO_PROCESS),
            "os.system": _deny(_NO_PROCESS),
            "os.exec": _deny(_NO_PROCESS),
            "os.posix_spawn": _deny(_NO_PROCESS),
            "os.spawn": _deny(_NO_PROCESS),
            "os.fork": _deny(_NO_PROCESS),
            "os.forkpty": _deny(_NO_PROCESS),
            "os.startfile": _deny(_NO_PROCESS),
            "os.startfile/2": _deny(_NO_PROCESS),
            "_winapi.CreateProcess": _deny(_NO_PROCESS),
            "os.kill": _deny(_NO_SIGNAL),
            "os.killpg": _deny(_NO_SIGNAL),
            "_winapi.OpenProcess": _deny(_NO_SIGNAL),
            "_winapi.TerminateProcess": _deny(_NO_SIGNAL),
            "sys.remote_exec": _deny(_NO_PROCESS),
            "webbrowser.open": _deny("opening a web browser is disabled in the sandbox"),
            # network
            "socket.connect": _deny(_NO_NETWORK),
            "socket.bind": _deny(_NO_NETWORK),
            "socket.sendto": _deny(_NO_NETWORK),
            "socket.sendmsg": _deny(_NO_NETWORK),
            "socket.gethostbyname": _deny(_NO_NETWORK),
            "socket.gethostbyaddr": _deny(_NO_NETWORK),
            "socket.getnameinfo": _deny(_NO_NETWORK),
            "socket.sethostname": _deny(_NO_NETWORK),
            "socket.getaddrinfo": self._on_getaddrinfo,
            # native code / limits
            "ctypes.dlopen": self._on_dlopen,
            "ctypes.call_function": _deny(_NO_NATIVE),
            "ctypes.cdata": _deny(_NO_NATIVE),           # from_address(): raw memory access
            "ctypes.string_at": _deny(_NO_NATIVE),
            "ctypes.wstring_at": _deny(_NO_NATIVE),
            "ctypes.PyObj_FromPtr": _deny(_NO_NATIVE),
            "sqlite3.enable_load_extension": _deny(_NO_NATIVE),
            "sqlite3.load_extension": _deny(_NO_NATIVE),
            "resource.setrlimit": _deny("changing resource limits is disabled in the sandbox"),
            "resource.prlimit": _deny("changing resource limits is disabled in the sandbox"),
            # filesystem writes (reads are always allowed)
            "open": self._on_open,
            "os.remove": self._path_args((0, 1)),
            "os.rmdir": self._path_args((0, 1)),
            "os.mkdir": self._path_args((0, 2)),
            "os.chmod": self._path_args((0, 2)),
            "os.chown": self._path_args((0, 3)),
            "os.utime": self._path_args((0, 3)),
            "os.truncate": first,
            "os.chflags": first,
            "os.lchflags": first,
            "os.setxattr": first,
            "os.removexattr": first,
            "os.mkfifo": self._path_args((0, 2)),
            "os.mknod": self._path_args((0, 3)),
            "os.rename": self._path_args((0, 2), (1, 3)),
            "os.link": self._path_args((0, 2), (1, 3)),
            "os.symlink": self._path_args((1, 2)),
            "shutil.rmtree": self._path_args((0, 1)),
            "shutil.copyfile": self._path_args((1, None)),
            "shutil.copymode": self._path_args((1, None)),
            "shutil.copystat": self._path_args((1, None)),
            "shutil.copytree": self._path_args((1, None)),
            "shutil.move": self._path_args((0, None), (1, None)),
            "shutil.make_archive": first,
            "shutil.unpack_archive": self._on_unpack_archive,
            "_winapi.CopyFile2": self._path_args((1, None)),
            "_winapi.CreateJunction": self._path_args((0, None), (1, None)),
            "_winapi.CreateFile": self._on_winapi_create_file,
            "sqlite3.connect": self._on_sqlite_connect,
        }
        self._handlers = handlers

    # -- hook ------------------------------------------------------------------------------
    def hook(self, event: str, args: tuple) -> None:
        handler = self._handlers.get(event)
        if handler is None:
            if event.startswith("winreg."):
                self._deny(event, "Windows registry access is disabled in the sandbox")
            return
        state = self._state
        if getattr(state, "busy", False):
            return
        state.busy = True
        try:
            reason = handler(args)
        except Exception:  # noqa: BLE001 - fail closed
            reason = "the sandbox could not validate this operation"
        finally:
            state.busy = False
        if reason:
            self._deny(event, reason)

    def _deny(self, event: str, reason: str) -> None:
        self._rec.block(event)
        raise PermissionError(f"{SANDBOX_TAG} {event}: {reason}")

    # -- path checks -----------------------------------------------------------------------
    def _check_path(self, path: object, dir_fd: object = None) -> str | None:
        if path is None or isinstance(path, int):
            return None
        text = os.fsdecode(os.fspath(path))  # type: ignore[arg-type]
        if dir_fd is not None and not os.path.isabs(text):
            return "paths relative to a directory descriptor are not allowed in the sandbox"
        if self._paths.is_writable(text):
            return None
        return f"writing outside the sandbox is not allowed ({text})"

    def _path_args(self, *specs: tuple[int, int | None]):
        def handler(args: tuple) -> str | None:
            for path_index, fd_index in specs:
                if path_index >= len(args):
                    continue
                dir_fd = args[fd_index] if fd_index is not None and fd_index < len(args) else None
                reason = self._check_path(args[path_index], dir_fd)
                if reason:
                    return reason
            return None

        return handler

    def _on_open(self, args: tuple) -> str | None:
        path = args[0] if args else None
        if path is None or isinstance(path, int):
            return None
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        writes = (isinstance(flags, int) and bool(flags & _WRITE_FLAGS)) or (
            isinstance(mode, str) and any(c in mode for c in "wax+")
        )
        return self._check_path(path) if writes else None

    def _on_unpack_archive(self, args: tuple) -> str | None:
        extract_dir = args[1] if len(args) > 1 and args[1] is not None else os.getcwd()
        return self._check_path(extract_dir)

    def _on_winapi_create_file(self, args: tuple) -> str | None:
        access = args[1] if len(args) > 1 and isinstance(args[1], int) else 0
        disposition = args[3] if len(args) > 3 and isinstance(args[3], int) else 0
        if access & _WINAPI_WRITE_ACCESS or disposition in _WINAPI_CREATING_DISPOSITIONS:
            return self._check_path(args[0] if args else None)
        return None

    def _on_sqlite_connect(self, args: tuple) -> str | None:
        database = args[0] if args else None
        if database is None:
            return None
        text = os.fsdecode(os.fspath(database))
        if text in ("", ":memory:"):
            return None
        if text.startswith("file:"):
            if text.startswith("file::memory:") or "mode=memory" in text:
                return None
            return "SQLite URI databases are not allowed in the sandbox"
        return self._check_path(text)

    # -- network / native ------------------------------------------------------------------
    @staticmethod
    def _on_getaddrinfo(args: tuple) -> str | None:
        host = args[0] if args else None
        if host is None:
            return None
        if isinstance(host, (bytes, bytearray)):
            host = bytes(host).decode("ascii", "replace")
        if isinstance(host, str) and (host == "" or _is_numeric_host(host)):
            return None  # numeric address: no DNS query; the connect() itself is blocked
        return _NO_NETWORK

    @staticmethod
    def _on_dlopen(args: tuple) -> str | None:
        # `import ctypes` loads the main program (POSIX) or kernel32 (Windows) without calling anything;
        # every foreign call is blocked by "ctypes.call_function" anyway.
        name = args[0] if args else None
        if name is None or (isinstance(name, str) and name.lower() in _ALLOWED_NATIVE_LIBS):
            return None
        return _NO_NATIVE


# ---------------------------------------------------------------------------------------------
# Exceptions, tracebacks and return values
# ---------------------------------------------------------------------------------------------


class _Reporter:
    def __init__(self, paths: _ProjectPaths) -> None:
        self._paths = paths

    def describe(self, exc: BaseException) -> dict:
        file = line = None
        if isinstance(exc, SyntaxError):
            message = exc.msg if isinstance(exc.msg, str) and exc.msg else _safe_str(exc)
            rel = self._paths.rel(exc.filename) if exc.filename else None
            if rel is not None:
                file, line = rel, exc.lineno
        else:
            message = _safe_str(exc)
        if file is None:
            file, line = self.last_student_frame(exc.__traceback__)
        return {
            "type": type(exc).__name__,
            "message": _cap(message, MAX_MESSAGE_CHARS),
            "traceback": _cap(self.format_exception(exc), MAX_TRACEBACK_CHARS),
            "file": file,
            "line": line,
        }

    def last_student_frame(self, tb) -> tuple[str | None, int | None]:
        file = line = None
        while tb is not None:
            rel = self._paths.rel(tb.tb_frame.f_code.co_filename)
            if rel is not None:
                file, line = rel, tb.tb_lineno
            tb = tb.tb_next
        return file, line

    def format_exception(self, exc: BaseException) -> str:
        """CPython-like traceback restricted to student frames, paths relative to the project."""
        names: dict[str, str] = {}
        try:
            te = traceback.TracebackException.from_exception(exc)
            self._filter(te, set(), names)
            text = "".join(te.format())
        except Exception:  # noqa: BLE001
            return f"{type(exc).__name__}: {_safe_str(exc)}\n"
        return self._relativize(text, names)

    def stack_text(self, frame) -> str:
        """Student part of a live stack (used when reporting a timeout)."""
        try:
            kept = [fs for fs in traceback.extract_stack(frame) if self._paths.rel(fs.filename)]
            names = {fs.filename: self._paths.rel(fs.filename) or fs.filename for fs in kept}
            if not kept:
                return ""
            text = "Traceback (most recent call last):\n" + "".join(traceback.StackSummary.from_list(kept).format())
        except Exception:  # noqa: BLE001
            return ""
        return self._relativize(text, names)

    def _filter(self, te, seen: set[int], names: dict[str, str]) -> None:
        if te is None or id(te) in seen:
            return
        seen.add(id(te))
        kept = []
        for fs in te.stack:
            rel = self._paths.rel(fs.filename)
            if rel is not None:
                names[fs.filename] = rel
                kept.append(fs)
        te.stack = traceback.StackSummary.from_list(kept)
        filename = getattr(te, "filename", None)
        if isinstance(filename, str):
            rel = self._paths.rel(filename)
            if rel is not None:
                te.filename = rel
        self._filter(te.__cause__, seen, names)
        self._filter(te.__context__, seen, names)
        for sub in getattr(te, "exceptions", None) or ():
            self._filter(sub, seen, names)

    @staticmethod
    def _relativize(text: str, names: dict[str, str]) -> str:
        for absolute, rel in names.items():
            text = text.replace(f'File "{absolute}"', f'File "{rel}"')
        return text


def _describe_value(value: object) -> dict:
    type_name = type(value).__name__
    try:
        text = repr(value)
    except BaseException as exc:  # noqa: BLE001
        return {"return_repr": f"<repr() failed: {type(exc).__name__}>", "return_type": type_name, "return_literal": False}
    if not isinstance(text, str):
        text = _safe_str(text)
    literal = False
    if len(text) <= MAX_LITERAL_CHECK_CHARS:
        try:
            back = ast.literal_eval(text)
            literal = type(back) is type(value) and bool(back == value)
        except Exception:  # noqa: BLE001 - ValueError, SyntaxError, RecursionError, MemoryError...
            literal = False
    return {"return_repr": _cap(text, MAX_REPR_CHARS), "return_type": type_name, "return_literal": literal}


def _warm_up_traceback() -> None:
    """Import traceback's lazy helpers now, before student directories are put on sys.path."""
    try:
        raise NameError("name 'x' is not defined", name="x")
    except NameError as exc:
        try:
            "".join(traceback.TracebackException.from_exception(exc).format())
        except Exception:  # noqa: BLE001
            pass


def _empty_result(job: dict) -> dict:
    kind = job.get("kind")
    return {
        "id": str(job.get("id", "")),
        "kind": kind if kind in JOB_KINDS else "function",
        "status": "harness_error",
        "duration_ms": 0.0,
        "return_repr": None,
        "return_type": None,
        "return_literal": False,
        "import_stdout": "",
        "stdout": "",
        "stderr": "",
        "exit_code": None,
        "events": [],
        "exception": None,
        "truncated": False,
        "blocked_syscalls": [],
        "harness_error": None,
    }


def _write_result(fh, result: dict) -> None:
    data = json.dumps(result, ensure_ascii=True).encode("ascii")
    fh.seek(0)
    fh.truncate()
    fh.write(data)
    fh.flush()


# ---------------------------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------------------------


class _Runner:
    def __init__(self, spec: dict, result_fh) -> None:
        self.job: dict = spec["job"]
        self.kind: str = self.job.get("kind", "")
        self.paths = _ProjectPaths(spec["project_root"], list(spec.get("write_roots") or []))
        self.rec = _Recorder(
            self.paths,
            int(spec.get("max_events", DEFAULT_MAX_EVENTS)),
            int(spec.get("max_output_bytes", DEFAULT_MAX_BYTES)),
        )
        self.reporter = _Reporter(self.paths)
        self.target: str = os.path.abspath(spec["target"])
        self.cwd: str = spec.get("cwd") or os.path.dirname(self.target)
        self.timeout_s = float(self.job.get("timeout_s", 5.0))
        self.result = _empty_result(self.job)
        self.stem = os.path.splitext(os.path.basename(self.target))[0]
        self._fh = result_fh
        self._finish_lock = threading.Lock()
        self._finished = False
        self._t0 = time.perf_counter()
        self._main_ident = threading.get_ident()
        self._kept_streams: tuple = ()
        self._err: _OutStream | None = None

    # -- lifecycle ---------------------------------------------------------------------------
    def run(self) -> None:
        self._setup_io()
        os.chdir(self.cwd)
        sys.dont_write_bytecode = True
        self.rec.on_limit = self._on_output_limit
        builtins.print = _make_print(self.rec)
        builtins.input = _make_input(self.rec)
        os._exit = self._on_os_exit
        _warm_up_traceback()
        _disable_fork_exec(self.rec)
        sys.addaudithook(_Guard(self.paths, self.rec).hook)
        self._start_watchdog()
        runners = {"function": self._run_function, "script": self._run_script, "import": self._run_import}
        try:
            run = runners.get(self.kind)
            if run is None:
                self.result["harness_error"] = f"unknown job kind: {self.kind!r}"
            else:
                run()
        except BaseException as exc:  # noqa: BLE001 - a bug in the harness itself
            self.result["status"] = "harness_error"
            self.result["harness_error"] = f"harness failure: {type(exc).__name__}: {_safe_str(exc)}"
        self.finish()

    def finish(self, **overrides) -> None:
        """Write the result file once (first caller wins) and terminate the process immediately."""
        with self._finish_lock:
            if not self._finished:
                self._finished = True
                result = dict(self.result)
                result.update(overrides)
                rec = self.rec
                import_out = "".join(list(rec.stdout_parts["import"]))
                call_out = "".join(list(rec.stdout_parts["call"]))
                if self.kind == "function":
                    result["import_stdout"], result["stdout"] = import_out, call_out
                else:
                    result["import_stdout"] = import_out if self.kind == "import" else ""
                    result["stdout"] = import_out + call_out
                result["stderr"] = "".join(list(rec.stderr_parts))
                result["events"] = list(rec.events)
                result["blocked_syscalls"] = list(rec.blocked)
                result["truncated"] = bool(result.get("truncated") or rec.limit_hit)
                result["duration_ms"] = round((time.perf_counter() - self._t0) * 1000.0, 3)
                try:
                    _write_result(self._fh, result)
                except Exception:  # noqa: BLE001 - the parent reports a crash
                    pass
        _REAL_EXIT(0)

    def _setup_io(self) -> None:
        # keep the original stream objects alive: they own fds 0-2 and would close them when collected
        self._kept_streams = (sys.stdin, sys.stdout, sys.stderr, sys.__stdin__, sys.__stdout__, sys.__stderr__)
        out = _OutStream(1, "output", self.rec, "surrogateescape")
        err = _OutStream(2, "stderr", self.rec, "backslashreplace")
        inp = io.TextIOWrapper(io.open(0, "rb", closefd=False), encoding="utf-8", errors="surrogateescape", newline=None)
        sys.stdout = sys.__stdout__ = out
        sys.stderr = sys.__stderr__ = err
        sys.stdin = sys.__stdin__ = inp
        self._err = err

    def _start_watchdog(self) -> None:
        def watch() -> None:
            time.sleep(self.timeout_s)
            self._on_timeout()

        threading.Thread(target=watch, name="premoulinette-watchdog", daemon=True).start()

    # -- asynchronous endings ---------------------------------------------------------------
    def _on_timeout(self) -> None:
        frame = sys._current_frames().get(self._main_ident)
        file, line = self.rec.locate(frame) if frame is not None else (None, None)
        stack = self.reporter.stack_text(frame) if frame is not None else ""
        message = f"Execution time limit exceeded ({self.timeout_s:g} s)"
        exception = {
            "type": "TimeoutError",
            "message": message,
            "traceback": stack + f"TimeoutError: {message}\n",
            "file": file,
            "line": line,
        }
        self.finish(status="timeout", exception=exception, exit_code=None)

    def _on_output_limit(self) -> None:
        self.finish(status="output_limit", truncated=True)

    def _on_os_exit(self, status=0, *_args) -> None:
        try:
            code = int(status)
        except (TypeError, ValueError):
            code = 1
        if self.kind == "script":
            self.finish(status="ok", exit_code=code)
            return
        file, line = self.rec.locate(sys._getframe(1))
        exception = {"type": "SystemExit", "message": f"os._exit({code}) was called", "traceback": "", "file": file, "line": line}
        status_name = "exception" if self.rec.phase == "call" else "import_error"
        self.finish(status=status_name, exception=exception, exit_code=code)

    # -- jobs ----------------------------------------------------------------------------------
    def _import_target(self):
        """Import the target module from its file (status/exception recorded on failure)."""
        module_dir = os.path.dirname(self.target)
        for entry in (self.paths.root, module_dir):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        stem = self.stem
        name = stem if stem.isidentifier() and stem not in sys.modules else STUDENT_MODULE_PREFIX + re.sub(r"\W", "_", stem)
        spec = importlib.util.spec_from_file_location(name, self.target)
        if spec is None or spec.loader is None:
            self.result.update(status="harness_error", harness_error=f"cannot load module from {self.target}")
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # registered under its real stem when possible: sibling imports reuse it
        self.rec.phase = "import"
        try:
            spec.loader.exec_module(module)
        except SyntaxError as exc:
            sys.modules.pop(name, None)
            self.result.update(status="syntax_error", exception=self.reporter.describe(exc), exit_code=1)
            return None
        except BaseException as exc:  # noqa: BLE001 - student code may raise anything (EOFError, SystemExit...)
            sys.modules.pop(name, None)
            code = self._exit_code(exc, write=False) if isinstance(exc, SystemExit) else 1
            self.result.update(status="import_error", exception=self.reporter.describe(exc), exit_code=code)
            return None
        return module

    def _run_function(self) -> None:
        module = self._import_target()
        if module is None:
            return
        self.rec.phase = "call"
        try:
            args = [ast.literal_eval(a) for a in self.job.get("args") or []]
            kwargs = {str(k): ast.literal_eval(v) for k, v in (self.job.get("kwargs") or {}).items()}
        except Exception as exc:  # noqa: BLE001
            self.result.update(status="harness_error", harness_error=f"invalid literal argument: {_safe_str(exc)}")
            return
        name = self.job.get("function")
        try:
            func = getattr(module, name, _MISSING) if isinstance(name, str) else _MISSING
        except BaseException as exc:  # noqa: BLE001 - module-level __getattr__
            self.result.update(status="exception", exception=self.reporter.describe(exc))
            return
        if func is _MISSING:
            message = f"module {self.stem!r} has no attribute {name!r}"
            exception = {"type": "AttributeError", "message": message, "traceback": f"AttributeError: {message}\n", "file": None, "line": None}
            self.result.update(status="exception", exception=exception)
            return
        try:
            value = func(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001
            self.result.update(status="exception", exception=self.reporter.describe(exc))
            return
        self.result.update(status="ok", **_describe_value(value))

    def _run_import(self) -> None:
        if self._import_target() is not None:
            self.result.update(status="ok", exit_code=0)

    def _run_script(self) -> None:
        self.rec.phase = "call"
        try:  # like `python file.py`: argv[0] is the path as typed from the working directory
            argv0 = os.path.relpath(self.target, self.cwd)
        except ValueError:  # another drive (Windows)
            argv0 = self.target
        sys.argv = [argv0] + [str(a) for a in self.job.get("argv") or []]
        sys.path.insert(0, os.path.dirname(self.target))  # like `python file.py`
        exit_code = 0
        try:
            self._exec_as_main()
            self.result["status"] = "ok"
        except SystemExit as exc:
            exit_code = self._exit_code(exc, write=True)
            self.result["status"] = "ok"
        except BaseException as exc:  # noqa: BLE001 - uncaught exception: traceback on stderr, exit 1
            info = self.reporter.describe(exc)
            self.result["status"] = "syntax_error" if isinstance(exc, SyntaxError) else "exception"
            self.result["exception"] = info
            self._write_stderr(info["traceback"])
            exit_code = 1
        self._interpreter_shutdown()
        self.result["exit_code"] = exit_code

    def _exec_as_main(self) -> None:
        """Run the script as the real ``__main__`` module, like ``python file.py``.

        (``runpy.run_path`` would be equivalent except that it forces ``sys.argv[0]`` to the absolute
        path, while ``python file.py`` keeps it as typed — scripts print it in usage messages.)
        """
        with io.open_code(self.target) as fh:
            source = fh.read()
        # dont_inherit: this file's `from __future__ import annotations` must not leak into student code
        code = compile(source, self.target, "exec", dont_inherit=True)
        main = types.ModuleType("__main__")
        main.__dict__.update(__file__=self.target, __cached__=None, __loader__=None, __package__=None, __spec__=None)
        sys.modules["__main__"] = main
        exec(code, main.__dict__)  # noqa: S102 - this IS the sandboxed execution of the student script

    # -- helpers -------------------------------------------------------------------------------
    def _exit_code(self, exc: SystemExit, *, write: bool) -> int:
        """`python file.py` semantics: None -> 0, int -> int, anything else printed on stderr -> 1."""
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return int(code)
        if write:
            self._write_stderr(_safe_str(code) + "\n")
        return 1

    def _write_stderr(self, text: str) -> None:
        if self._err is not None and text:
            try:
                self._err._pm_emit(text, (None, None), record=False)
            except Exception:  # noqa: BLE001 - the student may have closed stderr
                pass

    def _interpreter_shutdown(self) -> None:
        """Mimic interpreter exit: wait for non-daemon threads, then run atexit callbacks."""
        current = threading.current_thread()
        for thread in threading.enumerate():
            if thread is current or thread.daemon:
                continue
            try:
                thread.join()
            except BaseException:  # noqa: BLE001
                pass
        try:
            atexit._run_exitfuncs()
        except BaseException:  # noqa: BLE001
            pass


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        sys.stderr.write("usage: child.py <job.json> <result.json>\n")
        _REAL_EXIT(2)
    result_fh = open(argv[2], "wb")  # FIRST, before any guard is installed; kept open until exit
    try:
        with open(argv[1], "rb") as fh:
            spec = json.loads(fh.read().decode("utf-8"))
        runner = _Runner(spec, result_fh)
    except BaseException as exc:  # noqa: BLE001
        result = _empty_result({})
        result["harness_error"] = f"invalid job file: {type(exc).__name__}: {_safe_str(exc)}"
        _write_result(result_fh, result)
        _REAL_EXIT(0)
    runner.run()


if __name__ == "__main__":
    main(sys.argv)
