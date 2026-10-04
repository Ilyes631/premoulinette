"""PreMoulinette plan runner (sandbox side).

Usage:  python run_plan.py <plan.json> [--root DIR] [--sync-stdin]

STDLIB ONLY (runs inside the sandbox, possibly on another Python version). Reads a RunPlan JSON
document (same field names as ``premoulinette.runner.models``), runs every job in a fresh
``child.py`` interpreter with bounded parallelism, a per-job timeout (process-tree kill) and
per-stream output caps, then prints the RunResults JSON on stdout between
``@@PREMOULINETTE_RESULTS_BEGIN@@`` / ``@@PREMOULINETTE_RESULTS_END@@`` marker lines.

The project root is the current directory unless ``--root`` is given. ``--sync-stdin`` makes the
runner wait for one line on stdin before starting (the local sandbox uses it to put this process in
a Windows Job Object before any child is spawned).
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

BEGIN_MARKER = "@@PREMOULINETTE_RESULTS_BEGIN@@"
END_MARKER = "@@PREMOULINETTE_RESULTS_END@@"

CHILD_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "child.py")
KILL_GRACE_S = 1.0          # the child's own watchdog reports timeouts; the hard kill comes this much later
MAX_PARALLEL = 8
MAX_EVENTS = 5_000
MAX_BLOCKED = 50
MAX_RESULT_FILE_BYTES = 32 * 1024 * 1024
DEFAULT_TIMEOUT_S = 5.0
DEFAULT_MAX_OUTPUT = 65_536

JOB_KINDS = ("function", "script", "import")
STATUSES = ("ok", "exception", "timeout", "import_error", "syntax_error", "crash", "output_limit", "harness_error")
EVENT_KINDS = ("output", "input", "stderr")


# ---------------------------------------------------------------------------------------------
# Plan loading
# ---------------------------------------------------------------------------------------------


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(low, min(high, int(value)))


def _str_list(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _normalize_job(index: int, raw: object) -> dict:
    if not isinstance(raw, dict):
        return {"kind": "function", "id": f"job{index}", "timeout_s": DEFAULT_TIMEOUT_S, "_invalid": "job is not an object"}
    kind = raw.get("kind")
    job: dict = {"kind": kind if kind in JOB_KINDS else "function", "id": str(raw.get("id") or f"job{index}")}
    timeout = raw.get("timeout_s", DEFAULT_TIMEOUT_S)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout != timeout:
        timeout = DEFAULT_TIMEOUT_S
    job["timeout_s"] = max(0.05, min(600.0, float(timeout)))
    if kind not in JOB_KINDS:
        job["_invalid"] = f"unknown job kind: {kind!r}"
    elif kind == "script":
        job["script_path"] = raw.get("script_path")
        job["argv"] = _str_list(raw.get("argv"))
        stdin = raw.get("stdin", "")
        job["stdin"] = stdin if isinstance(stdin, str) else ""
    else:
        job["module_path"] = raw.get("module_path")
        if kind == "function":
            job["function"] = raw.get("function")
            job["args"] = _str_list(raw.get("args"))
            kwargs = raw.get("kwargs")
            job["kwargs"] = {str(k): str(v) for k, v in kwargs.items()} if isinstance(kwargs, dict) else {}
    return job


def load_plan(path: str) -> dict:
    with open(path, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("the plan must be a JSON object")
    jobs = data.get("jobs") or []
    if not isinstance(jobs, list):
        raise ValueError("'jobs' must be a list")
    cwd_mode = data.get("cwd_mode", "script_dir")
    return {
        "jobs": [_normalize_job(i, j) for i, j in enumerate(jobs)],
        "max_parallel": _bounded_int(data.get("max_parallel"), 4, 1, MAX_PARALLEL),
        "max_output_bytes": _bounded_int(data.get("max_output_bytes"), DEFAULT_MAX_OUTPUT, 1024, 64 * 1024 * 1024),
        "cwd_mode": cwd_mode if cwd_mode in ("script_dir", "project_root") else "script_dir",
    }


def resolve_inside(root: str, rel: object) -> tuple[str | None, str | None]:
    """Absolute path of a project-relative POSIX path, or (None, problem) if invalid/outside/missing."""
    if not isinstance(rel, str) or not rel.strip() or "\x00" in rel:
        return None, "missing or invalid file path"
    norm = rel.replace("\\", "/")
    if norm.startswith("/") or (os.name == "nt" and ":" in norm):
        return None, f"absolute paths are not allowed: {rel}"
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None, f"path escapes the project: {rel}"
    target = os.path.join(root, *parts)
    real_root = os.path.normcase(os.path.realpath(root))
    real_target = os.path.normcase(os.path.realpath(target))
    if not real_target.startswith(real_root.rstrip(os.sep) + os.sep):
        return None, f"path escapes the project: {rel}"
    if not os.path.isfile(target):
        return None, f"file not found: {rel}"
    return target, None


# ---------------------------------------------------------------------------------------------
# Child process execution
# ---------------------------------------------------------------------------------------------


class Capture:
    """What the parent observed for one child process."""

    def __init__(self) -> None:
        self.stdout = b""
        self.stderr = b""
        self.returncode: int | None = None
        self.timed_out = False
        self.limit_hit = False
        self.duration_ms = 0.0
        self.error: str | None = None


class _CappedReader(threading.Thread):
    """Drains one pipe, keeping at most `cap` bytes; calls `on_limit` once when the cap is exceeded."""

    def __init__(self, stream, cap: int, on_limit) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._cap = cap
        self._on_limit = on_limit
        self.data = bytearray()
        self.exceeded = False

    def run(self) -> None:
        try:
            while True:
                chunk = self._stream.read1(65536)
                if not chunk:
                    break
                if self.exceeded:
                    continue
                room = self._cap - len(self.data)
                if len(chunk) > room:
                    self.data += chunk[:room]
                    self.exceeded = True
                    self._on_limit()
                else:
                    self.data += chunk
        except (OSError, ValueError):
            pass
        finally:
            try:
                self._stream.close()
            except OSError:
                pass


def _feed_stdin(stream, data: bytes) -> None:
    try:
        if data:
            stream.write(data)
    except (OSError, ValueError):
        pass  # the child exited without reading everything
    finally:
        try:
            stream.close()
        except OSError:
            pass


_DETACHED_PROCESS = 0x00000008


def _popen_isolation() -> dict:
    if os.name == "nt":
        # no console at all: no window, and no conhost.exe counted in the Job Object's process limit
        return {"creationflags": _DETACHED_PROCESS}
    return {"start_new_session": True}


def kill_tree(proc: subprocess.Popen) -> None:
    """Kill a child and all its descendants (best effort, idempotent)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        taskkill = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "taskkill.exe")
        try:
            subprocess.run(
                [taskkill, "/F", "/T", "/PID", str(proc.pid)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, **_popen_isolation(),
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


def run_child(cmd: list[str], cwd: str, env: dict, stdin_bytes: bytes, timeout_s: float, cap: int) -> Capture:
    capture = Capture()
    start = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            **_popen_isolation(),
        )
    except OSError as exc:
        capture.error = f"could not start the child process: {exc}"
        return capture
    limit_event = threading.Event()

    def on_limit() -> None:
        limit_event.set()
        kill_tree(proc)

    readers = [_CappedReader(proc.stdout, cap, on_limit), _CappedReader(proc.stderr, cap, on_limit)]
    writer = threading.Thread(target=_feed_stdin, args=(proc.stdin, stdin_bytes), daemon=True)
    for thread in (*readers, writer):
        thread.start()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        capture.timed_out = True
        kill_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    capture.duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
    for reader in readers:
        reader.join(timeout=5)
    writer.join(timeout=1)
    capture.stdout = bytes(readers[0].data)
    capture.stderr = bytes(readers[1].data)
    capture.limit_hit = limit_event.is_set()
    capture.returncode = proc.returncode
    return capture


def load_child_result(path: str) -> dict | None:
    try:
        size = os.path.getsize(path)
        if size == 0 or size > MAX_RESULT_FILE_BYTES:
            return None
        with open(path, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------------------------
# Result sanitizing / merging (the child's file is written by student-controlled code)
# ---------------------------------------------------------------------------------------------


def _clean(text: str) -> str:
    """Drop lone surrogates so the result is always valid UTF-8 JSON."""
    return text.encode("utf-8", "replace").decode("utf-8")


def _opt_str(value: object) -> str | None:
    return _clean(value) if isinstance(value, str) else None


def _opt_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        return 0.0
    return float(value)


def _event(raw: object) -> dict | None:
    if not isinstance(raw, dict) or raw.get("kind") not in EVENT_KINDS or not isinstance(raw.get("text"), str):
        return None
    return {"kind": raw["kind"], "text": _clean(raw["text"]), "file": _opt_str(raw.get("file")), "line": _opt_int(raw.get("line"))}


def _exception(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {
        "type": _opt_str(raw.get("type")) or "Exception",
        "message": _opt_str(raw.get("message")) or "",
        "traceback": _opt_str(raw.get("traceback")) or "",
        "file": _opt_str(raw.get("file")),
        "line": _opt_int(raw.get("line")),
    }


def sanitize_child(child: dict) -> dict:
    status = child.get("status")
    events = [e for e in (_event(raw) for raw in (child.get("events") or [])[:MAX_EVENTS]) if e is not None]
    blocked = [_clean(s) for s in (child.get("blocked_syscalls") or []) if isinstance(s, str)][:MAX_BLOCKED]
    return {
        "status": status if status in STATUSES else "harness_error",
        "duration_ms": _number(child.get("duration_ms")),
        "return_repr": _opt_str(child.get("return_repr")),
        "return_type": _opt_str(child.get("return_type")),
        "return_literal": child.get("return_literal") is True,
        "import_stdout": _opt_str(child.get("import_stdout")) or "",
        "stdout": _opt_str(child.get("stdout")) or "",
        "exit_code": _opt_int(child.get("exit_code")),
        "events": events,
        "exception": _exception(child.get("exception")),
        "truncated": child.get("truncated") is True,
        "blocked_syscalls": blocked,
        "harness_error": _opt_str(child.get("harness_error")),
    }


def base_result(job: dict) -> dict:
    return {
        "id": job["id"], "kind": job["kind"], "status": "harness_error", "duration_ms": 0.0,
        "return_repr": None, "return_type": None, "return_literal": False, "import_stdout": "",
        "stdout": "", "stderr": "", "exit_code": None, "events": [], "exception": None,
        "truncated": False, "blocked_syscalls": [], "harness_error": None,
    }


def harness_error_result(job: dict, message: str) -> dict:
    result = base_result(job)
    result["harness_error"] = message
    return result


def merge_result(job: dict, capture: Capture, child: dict | None) -> dict:
    """Combine the child's report with what the parent observed (raw streams are authoritative)."""
    result = base_result(job)
    raw_out = capture.stdout.decode("utf-8", "replace")
    raw_err = capture.stderr.decode("utf-8", "replace")
    if child is not None:
        result.update(sanitize_child(child))
    else:
        result["duration_ms"] = capture.duration_ms
        if capture.error:
            result["harness_error"] = capture.error
        elif capture.timed_out:
            result["status"] = "timeout"
        elif capture.limit_hit:
            result["status"] = "output_limit"
        else:
            result["status"] = "crash"
            result["exit_code"] = capture.returncode
            result["harness_error"] = (
                f"the child process exited with code {capture.returncode} without reporting a result"
            )
    if capture.timed_out:
        result["status"] = "timeout"
    if capture.limit_hit:
        result["status"] = "output_limit"
    if result["status"] == "timeout":
        result["exit_code"] = None
    result["truncated"] = bool(result["truncated"] or capture.limit_hit or result["status"] == "output_limit")
    kind = job["kind"]
    if kind == "function":
        prefix = result["import_stdout"]
        if child is None:
            result["stdout"] = raw_out
        elif raw_out.startswith(prefix):
            result["stdout"] = raw_out[len(prefix):]
    elif kind == "import":
        result["stdout"] = result["import_stdout"] = raw_out
    else:
        result["stdout"] = raw_out
    result["stderr"] = raw_err
    return result


# ---------------------------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------------------------


def _child_env(scratch: str) -> dict:
    env = dict(os.environ)
    for key in ("TMP", "TEMP", "TMPDIR"):
        env[key] = scratch
    return env


def run_job(index: int, job: dict, plan: dict, root: str, private_dir: str) -> dict:
    if job.get("_invalid"):
        return harness_error_result(job, job["_invalid"])
    rel = job.get("script_path") if job["kind"] == "script" else job.get("module_path")
    target, problem = resolve_inside(root, rel)
    if target is None:
        return harness_error_result(job, problem or "invalid file path")
    cwd = os.path.dirname(target) if plan["cwd_mode"] == "script_dir" else root
    job_dir = os.path.join(private_dir, f"job{index}")      # NOT writable by the child (results live here)
    scratch = os.path.join(private_dir, f"scratch{index}")  # the child's TMP dir (writable)
    os.mkdir(job_dir)
    os.mkdir(scratch)
    job_file = os.path.join(job_dir, "job.json")
    result_file = os.path.join(job_dir, "result.json")
    spec = {
        "job": job, "project_root": root, "target": target, "cwd": cwd, "write_roots": [root, scratch],
        "max_output_bytes": plan["max_output_bytes"], "max_events": MAX_EVENTS,
    }
    with open(job_file, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=True)
    cmd = [sys.executable, "-I", "-X", "utf8", CHILD_SCRIPT, job_file, result_file]
    stdin_bytes = job.get("stdin", "").encode("utf-8", "replace") if job["kind"] == "script" else b""
    capture = run_child(cmd, cwd, _child_env(scratch), stdin_bytes, job["timeout_s"] + KILL_GRACE_S, plan["max_output_bytes"])
    return merge_result(job, capture, load_child_result(result_file))


def _run_job_safe(index: int, job: dict, plan: dict, root: str, private_dir: str) -> dict:
    try:
        return run_job(index, job, plan, root, private_dir)
    except Exception as exc:  # noqa: BLE001 - never lose the other results
        return harness_error_result(job, f"harness failure: {type(exc).__name__}: {exc}")


def run_all(plan: dict, root: str, private_dir: str) -> list[dict]:
    jobs = plan["jobs"]
    if not jobs:
        return []
    workers = max(1, min(plan["max_parallel"], MAX_PARALLEL, len(jobs)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="premoulinette-job") as pool:
        futures = [pool.submit(_run_job_safe, i, job, plan, root, private_dir) for i, job in enumerate(jobs)]
        return [f.result() for f in futures]


def remove_tree(path: str, attempts: int = 10) -> None:
    def make_writable(func, target, _exc) -> None:
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass

    kwargs = {"onexc": make_writable} if sys.version_info >= (3, 12) else {"onerror": make_writable}
    for attempt in range(attempts):
        try:
            shutil.rmtree(path, **kwargs)
        except OSError:
            pass
        if not os.path.exists(path):
            return
        time.sleep(0.05 * (attempt + 1))  # Windows: files of a just-killed child may still be locked


def emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    data = ("\n" + BEGIN_MARKER + "\n" + text + "\n" + END_MARKER + "\n").encode("ascii")
    out = getattr(sys.stdout, "buffer", None)
    if out is not None:
        out.write(data)
        out.flush()
    else:
        sys.stdout.write(data.decode("ascii"))
        sys.stdout.flush()


def _parse_args(argv: list[str]) -> tuple[str, str, bool]:
    plan_path: str | None = None
    root = os.getcwd()
    sync = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--sync-stdin":
            sync = True
        elif arg == "--root" and i + 1 < len(argv):
            root = argv[i + 1]
            i += 1
        elif plan_path is None:
            plan_path = arg
        else:
            raise SystemExit(f"unexpected argument: {arg}")
        i += 1
    if plan_path is None:
        raise SystemExit("usage: run_plan.py <plan.json> [--root DIR] [--sync-stdin]")
    return plan_path, os.path.abspath(root), sync


def main(argv: list[str] | None = None) -> int:
    plan_path, root, sync = _parse_args(sys.argv[1:] if argv is None else argv)
    if sync:
        try:
            sys.stdin.buffer.readline()
        except (OSError, ValueError, AttributeError):
            pass
    start = time.perf_counter()
    payload: dict = {"results": [], "python_version": "%d.%d.%d" % sys.version_info[:3], "total_ms": 0.0, "errors": []}
    try:
        plan = load_plan(plan_path)
    except (OSError, ValueError) as exc:
        payload["errors"].append(f"invalid run plan: {exc}")
        emit(payload)
        return 2
    private_dir = tempfile.mkdtemp(prefix="pm-run-")
    try:
        payload["results"] = run_all(plan, root, private_dir)
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"harness failure: {type(exc).__name__}: {exc}")
    finally:
        remove_tree(private_dir)
    payload["total_ms"] = round((time.perf_counter() - start) * 1000.0, 3)
    emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
