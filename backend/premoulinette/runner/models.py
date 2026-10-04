"""Execution contract between the backend and the sandboxed harness.

The backend builds a :class:`RunPlan` (pure data, JSON), the sandbox (Docker container or local
restricted subprocess) runs ``harness/run_plan.py`` on it, and returns a :class:`RunResults`.
Each job runs in its own fresh Python child process inside the sandbox (no state leaks between tests).

NOTE: ``premoulinette/languages/python/harness/*.py`` must stay **stdlib-only** and must not import
``premoulinette`` (it runs inside the sandbox, possibly with a different Python version). It reads and
writes plain JSON with the exact same field names as these models.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FunctionJob(BaseModel):
    kind: Literal["function"] = "function"
    id: str                          # == FunctionTest.id (or a generated id for derived/heuristic tests)
    module_path: str                 # POSIX path relative to the project root inside the sandbox
    function: str
    args: list[str] = Field(default_factory=list)       # python literal sources (ast.literal_eval'd in the child)
    kwargs: dict[str, str] = Field(default_factory=dict)
    timeout_s: float = 5.0


class ScriptJob(BaseModel):
    kind: Literal["script"] = "script"
    id: str
    script_path: str                 # POSIX path relative to the project root
    argv: list[str] = Field(default_factory=list)
    stdin: str = ""
    timeout_s: float = 5.0


class ImportJob(BaseModel):
    """Import a module with empty stdin and record side effects (prints, input() calls, crashes)."""
    kind: Literal["import"] = "import"
    id: str
    module_path: str
    timeout_s: float = 5.0


Job = FunctionJob | ScriptJob | ImportJob


class RunPlan(BaseModel):
    jobs: list[FunctionJob | ScriptJob | ImportJob] = Field(default_factory=list)
    max_parallel: int = 4
    max_output_bytes: int = 65536    # per stream per job; output beyond is truncated and flagged
    cwd_mode: Literal["script_dir", "project_root"] = "script_dir"


class RawEvent(BaseModel):
    """Instrumented I/O event recorded by the child (print / input / stderr write)."""
    kind: Literal["output", "input", "stderr"]
    text: str
    file: str | None = None          # project-relative path of the student frame that produced it
    line: int | None = None


class RawException(BaseModel):
    type: str
    message: str
    traceback: str = ""              # filtered: only frames inside the project
    file: str | None = None          # last student frame
    line: int | None = None


JobStatus = Literal["ok", "exception", "timeout", "import_error", "syntax_error", "crash", "output_limit", "harness_error"]


class JobResult(BaseModel):
    id: str
    kind: Literal["function", "script", "import"]
    status: JobStatus
    duration_ms: float = 0
    # function jobs
    return_repr: str | None = None
    return_type: str | None = None   # type(x).__name__ ; "NoneType" for None
    return_literal: bool = False     # True if ast.literal_eval(return_repr) round-trips
    import_stdout: str = ""          # stdout produced while importing the module
    # all jobs
    stdout: str = ""                 # function: stdout during the call ; script: whole raw stdout
    stderr: str = ""
    exit_code: int | None = None     # script/import jobs
    events: list[RawEvent] = Field(default_factory=list)
    exception: RawException | None = None
    truncated: bool = False
    blocked_syscalls: list[str] = Field(default_factory=list)   # e.g. ["socket.connect", "subprocess.Popen"]
    harness_error: str | None = None


class RunResults(BaseModel):
    results: list[JobResult] = Field(default_factory=list)
    python_version: str | None = None
    sandbox_mode: Literal["docker", "local"] = "local"
    total_ms: float = 0
    errors: list[str] = Field(default_factory=list)
