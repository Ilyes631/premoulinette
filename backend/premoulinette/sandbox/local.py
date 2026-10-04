"""Local sandbox ("Developer mode"): runs the harness directly on this machine, with best-effort isolation.

For every run:
* the snapshot is copied to a fresh temporary directory (``.git`` / ``__pycache__`` / symlinks skipped),
  together with the harness and the plan JSON; the directory is always removed afterwards;
* the harness runs with the *base* interpreter (not the backend venv) in isolated mode and a minimal
  environment: SYSTEMROOT, PATH (python dir only), TEMP/TMP (private dir), PYTHONIOENCODING, PYTHONUTF8 —
  nothing else, so secrets such as ``ANTHROPIC_API_KEY`` never reach student code;
* Windows: the harness is put in a Job Object (kill-on-close, 32 processes, 512 MB) *before* it starts any
  child (``--sync-stdin`` handshake); POSIX: rlimits + a new session;
* a global hard timeout kills the whole process tree.

Inside, ``child.py`` blocks network, process creation and writes outside the sandbox with audit hooks.
None of this is a security boundary comparable to a container: :meth:`LocalSandbox.info` says so.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from premoulinette.results.models import SandboxInfo
from premoulinette.runner.models import RunPlan, RunResults
from premoulinette.sandbox import common
from premoulinette.sandbox.base import copy_harness, copy_project, write_plan
from premoulinette.sandbox.procutil import collect, detached_flags, kill_tree

GLOBAL_SLACK_S = 15.0
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
MAX_PROCESSES = 32
# POSIX RLIMIT_AS is per process and counts *virtual* memory (thread stacks, malloc arenas of the
# multi-threaded harness), so it is set higher than the Windows job-wide committed-memory limit.
POSIX_ADDRESS_SPACE_LIMIT = 1024 * 1024 * 1024
POSIX_FILE_SIZE_LIMIT = 64 * 1024 * 1024
POSIX_OPEN_FILES = 256
COLLECT_TIMEOUT_S = 10.0
SYNC_TOKEN = b"go\n"


def base_python() -> str:
    """The base interpreter (outside the backend venv: student code must not see its packages)."""
    exe = getattr(sys, "_base_executable", None) or sys.executable
    return exe if exe and os.path.isfile(exe) else sys.executable


def minimal_env(python: str, temp_dir: Path) -> dict[str, str]:
    """The only environment variables the harness (and student code) receives."""
    env = {
        "PATH": os.path.dirname(os.path.abspath(python)),
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT") or os.environ.get("SystemRoot") or r"C:\Windows"
    else:
        env["TMPDIR"] = str(temp_dir)  # POSIX name of TEMP
    return env


def _posix_preexec(cpu_seconds: int):  # pragma: no cover - POSIX only
    def apply() -> None:
        import resource

        limits = [
            ("RLIMIT_AS", POSIX_ADDRESS_SPACE_LIMIT),
            ("RLIMIT_CPU", cpu_seconds),
            ("RLIMIT_CORE", 0),
            ("RLIMIT_FSIZE", POSIX_FILE_SIZE_LIMIT),
            ("RLIMIT_NOFILE", POSIX_OPEN_FILES),
        ]
        for name, value in limits:
            res = getattr(resource, name, None)
            if res is None:
                continue
            try:
                _soft, hard = resource.getrlimit(res)
                new = value if hard == resource.RLIM_INFINITY else min(value, hard)
                resource.setrlimit(res, (new, new))
            except (ValueError, OSError):
                pass

    return apply


class LocalSandbox:
    """Developer mode sandbox (see module docstring)."""

    mode = "local"

    def __init__(self, *, python: str | None = None, keep_dir: bool = False) -> None:
        self.python = python or base_python()
        self.keep_dir = keep_dir                 # tests/debugging only
        self.last_dir: Path | None = None        # temp dir of the last run (removed unless keep_dir)
        self._python_version: str | None = None

    # ------------------------------------------------------------------------------------------
    def info(self) -> SandboxInfo:
        windows = os.name == "nt"
        warnings = [
            "Developer mode: the student code runs directly on this computer, under your user account, "
            "not inside a container.",
            "Network access, process creation and writes outside the temporary copy are blocked by Python "
            "audit hooks inside the harness. This is a best-effort guard, not a security boundary: the code "
            "can still read your files. Use Docker safe mode for code you do not trust.",
        ]
        if windows:
            warnings.append(
                f"A Windows Job Object limits each run to {MAX_PROCESSES} processes and "
                f"{MEMORY_LIMIT_BYTES // (1024 * 1024)} MB of memory and kills every remaining process at the end."
            )
        else:
            warnings.append(
                f"POSIX resource limits (address space {POSIX_ADDRESS_SPACE_LIMIT // (1024 * 1024)} MB per process, "
                "CPU time, file size) "
                "and a separate process session are applied; the number of processes is not limited."
            )
        return SandboxInfo(
            mode="local",
            image=None,
            python_version=self._python_version or "%d.%d.%d" % sys.version_info[:3],
            network=False,
            limits={
                "memory_mb": (MEMORY_LIMIT_BYTES if windows else POSIX_ADDRESS_SPACE_LIMIT) // (1024 * 1024),
                "max_processes": MAX_PROCESSES if windows else None,
                "isolation": "windows-job-object" if windows else "posix-rlimits",
                "global_timeout_slack_s": GLOBAL_SLACK_S,
                "network": "blocked by audit hook",
                "filesystem": "temporary copy of the project (writes elsewhere blocked by audit hook)",
            },
            warnings=warnings,
        )

    # ------------------------------------------------------------------------------------------
    def run(self, plan: RunPlan, project_root: Path) -> RunResults:
        start = time.perf_counter()
        if not plan.jobs:
            return RunResults(sandbox_mode="local", python_version=self._python_version)
        tmp = Path(tempfile.mkdtemp(prefix="pm-local-"))
        self.last_dir = tmp
        try:
            try:
                work = tmp / "work"
                copy_project(Path(project_root), work)
                harness = copy_harness(tmp / "harness")
                plan_path = write_plan(plan, tmp / "plan")
                temp_dir = tmp / "tmp"
                temp_dir.mkdir()
            except OSError as exc:
                return common.failed_results(
                    plan, "local", f"could not prepare the sandbox directory: {exc}",
                    total_ms=_ms(start),
                )
            results = self._execute(plan, work, harness, plan_path, temp_dir, start)
        finally:
            if not self.keep_dir:
                common.remove_tree(tmp)
        if results.python_version:
            self._python_version = results.python_version
        return results

    def _execute(self, plan: RunPlan, work: Path, harness: Path, plan_path: Path, temp_dir: Path,
                 start: float) -> RunResults:
        cmd = [
            self.python, "-I", "-X", "utf8", "-B",
            str(harness / common.RUN_PLAN_NAME), str(plan_path), "--root", str(work), "--sync-stdin",
        ]
        budget = common.global_timeout(plan, GLOBAL_SLACK_S)
        kwargs: dict = {
            "cwd": str(work), "env": minimal_env(self.python, temp_dir),
            "stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
        }
        if os.name == "nt":
            kwargs["creationflags"] = detached_flags() | subprocess.CREATE_NEW_PROCESS_GROUP
        else:  # pragma: no cover - POSIX only
            kwargs["start_new_session"] = True
            kwargs["preexec_fn"] = _posix_preexec(int(budget) + 5)
        errors: list[str] = []
        try:
            proc = subprocess.Popen(cmd, **kwargs)
        except OSError as exc:
            return common.failed_results(plan, "local", f"could not start the harness: {exc}", total_ms=_ms(start))
        job = self._contain(proc, errors)
        timed_out = False
        try:
            try:
                out, err = proc.communicate(input=SYNC_TOKEN, timeout=budget)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._kill(proc, job)
                out, err = collect(proc, COLLECT_TIMEOUT_S)
        finally:
            if proc.poll() is None:
                self._kill(proc, job)
            if job is not None:
                _close_job(job)  # KILL_ON_JOB_CLOSE: no descendant survives the run
        process_error = None
        if timed_out:
            process_error = f"global time limit exceeded ({budget:.0f} s): the whole run was killed"
            return common.failed_results(plan, "local", process_error, total_ms=_ms(start))
        if proc.returncode not in (0, None):
            process_error = f"the harness exited with code {proc.returncode}"
            tail = common.tail(err)
            if tail:
                process_error += f": {tail}"
        results = common.parse_results(
            out.decode("utf-8", "replace"), plan, "local", process_error=process_error, total_ms=_ms(start),
        )
        if errors:
            results.errors.extend(errors)
        return results

    # ------------------------------------------------------------------------------------------
    @staticmethod
    def _contain(proc: subprocess.Popen, errors: list[str]) -> int | None:
        """Windows: put the (still waiting) harness in a Job Object. Returns the job handle or None."""
        if os.name != "nt":
            return None
        from premoulinette.sandbox import winjob

        job = None
        try:
            job = winjob.create_job(max_processes=MAX_PROCESSES, memory_bytes=MEMORY_LIMIT_BYTES)
            handle = getattr(proc, "_handle", None)
            if handle is not None:
                winjob.assign(job, int(handle))
            else:
                winjob.assign(job, pid=proc.pid)
            return job
        except OSError as exc:
            errors.append(
                f"Windows Job Object unavailable ({exc}); process/memory limits were not enforced for this run"
            )
            if job is not None:
                _close_job(job)
            return None

    @staticmethod
    def _kill(proc: subprocess.Popen, job: int | None) -> None:
        if job is not None:
            from premoulinette.sandbox import winjob

            try:
                winjob.terminate(job)
            except OSError:
                pass
        kill_tree(proc)


def _close_job(job: int) -> None:
    from premoulinette.sandbox import winjob

    try:
        winjob.close(job)
    except OSError:
        pass


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)
