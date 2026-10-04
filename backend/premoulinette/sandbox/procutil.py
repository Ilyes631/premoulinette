"""Small process helpers: console-less creation flags, process-tree kill, bounded output collection."""
from __future__ import annotations

import os
import signal
import subprocess

_DETACHED_PROCESS = 0x00000008


def no_window_flags() -> int:
    """Creation flags for helper commands (docker CLI...) so no console window flashes on Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def detached_flags() -> int:
    """Windows: start without any console (no conhost.exe, which would count in the job's process limit)."""
    return _DETACHED_PROCESS if os.name == "nt" else 0


def kill_tree(proc: subprocess.Popen) -> None:
    """Kill a process and its descendants (best effort, idempotent)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        taskkill = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "taskkill.exe")
        try:
            subprocess.run(
                [taskkill, "/F", "/T", "/PID", str(proc.pid)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, creationflags=no_window_flags(),
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


def terminate_group(proc: subprocess.Popen) -> None:
    """POSIX: ask the process group to stop (the harness kills its own children on SIGTERM)."""
    if os.name == "nt" or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        pass


def collect(proc: subprocess.Popen, timeout: float) -> tuple[bytes, bytes]:
    """Finish ``communicate()`` after a kill; give up (empty output) if pipes stay open too long."""
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass
        return b"", b""
    except (OSError, ValueError):
        return b"", b""
    return out or b"", err or b""
