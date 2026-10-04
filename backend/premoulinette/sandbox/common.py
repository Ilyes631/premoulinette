"""Helpers shared by the Docker and local sandboxes: harness location, result parsing, budgets, cleanup."""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from premoulinette.runner.models import JobResult, RunPlan, RunResults

# Must match ``languages/python/harness/run_plan.py`` (checked by the harness tests).
BEGIN_MARKER = "@@PREMOULINETTE_RESULTS_BEGIN@@"
END_MARKER = "@@PREMOULINETTE_RESULTS_END@@"
HARNESS_MAX_PARALLEL = 8
HARNESS_KILL_GRACE_S = 1.0

HARNESS_DIR = Path(__file__).resolve().parents[1] / "languages" / "python" / "harness"
HARNESS_FILES = ("run_plan.py", "child.py")
RUN_PLAN_NAME = "run_plan.py"

# Per-job allowance on top of the job timeout: interpreter start-up, kill grace, result merge.
PER_JOB_OVERHEAD_S = HARNESS_KILL_GRACE_S + 1.0
STDERR_TAIL_CHARS = 2000


def harness_path(name: str) -> Path:
    return HARNESS_DIR / name


def effective_parallelism(plan: RunPlan) -> int:
    return max(1, min(plan.max_parallel, HARNESS_MAX_PARALLEL, len(plan.jobs) or 1))


def global_timeout(plan: RunPlan, slack_s: float) -> float:
    """Wall-clock budget for a whole plan.

    List scheduling of jobs on ``p`` workers finishes within ``sum(cost) / p + max(cost)``; the
    slack covers sandbox start-up (container creation, project copy, ...).
    """
    if not plan.jobs:
        return slack_s
    costs = [job.timeout_s + PER_JOB_OVERHEAD_S for job in plan.jobs]
    return sum(costs) / effective_parallelism(plan) + max(costs) + slack_s


def failed_job(job_id: str, kind: str, message: str) -> JobResult:
    return JobResult(id=job_id, kind=kind, status="harness_error", harness_error=message)  # type: ignore[arg-type]


def failed_results(plan: RunPlan, mode: str, error: str, *, total_ms: float = 0.0,
                   python_version: str | None = None) -> RunResults:
    """Every job marked ``harness_error`` with the same explanation."""
    return RunResults(
        results=[failed_job(job.id, job.kind, error) for job in plan.jobs],
        python_version=python_version,
        sandbox_mode=mode,  # type: ignore[arg-type]
        total_ms=total_ms,
        errors=[error],
    )


def extract_payload(stdout: str) -> str | None:
    """JSON text between the last BEGIN marker and the following END marker, if any."""
    start = stdout.rfind(BEGIN_MARKER)
    if start < 0:
        return None
    start += len(BEGIN_MARKER)
    end = stdout.find(END_MARKER, start)
    if end < 0:
        return None
    return stdout[start:end].strip()


def _parse_job_results(raw_results: object, errors: list[str]) -> list[JobResult]:
    results: list[JobResult] = []
    if not isinstance(raw_results, list):
        errors.append("the harness returned no result list")
        return results
    for index, raw in enumerate(raw_results):
        try:
            results.append(JobResult.model_validate(raw))
        except ValidationError as exc:
            job_id = raw.get("id") if isinstance(raw, dict) else None
            errors.append(f"invalid result #{index} ({job_id!r}) from the harness: {exc.error_count()} error(s)")
    return results


def parse_results(stdout: str, plan: RunPlan, mode: str, *, process_error: str | None = None,
                  total_ms: float = 0.0) -> RunResults:
    """Build :class:`RunResults` from the harness stdout.

    Jobs without a (valid) result are reported as ``harness_error`` so callers always get one
    result per planned job.
    """
    payload = extract_payload(stdout)
    if payload is None:
        reason = process_error or "the sandbox produced no result markers"
        return failed_results(plan, mode, f"sandbox failure: {reason}", total_ms=total_ms)
    try:
        data = json.loads(payload)
    except ValueError as exc:
        return failed_results(plan, mode, f"sandbox failure: unreadable results ({exc})", total_ms=total_ms)
    if not isinstance(data, dict):
        return failed_results(plan, mode, "sandbox failure: unreadable results (not an object)", total_ms=total_ms)
    errors = [str(e) for e in data.get("errors") or [] if isinstance(e, str)]
    results = _parse_job_results(data.get("results"), errors)
    by_id = {r.id: r for r in results}
    missing = [job for job in plan.jobs if job.id not in by_id]
    for job in missing:
        results.append(failed_job(job.id, job.kind, "the sandbox returned no result for this job"))
    if process_error:
        errors.append(process_error)
    version = data.get("python_version")
    harness_ms = data.get("total_ms")
    return RunResults(
        results=results,
        python_version=version if isinstance(version, str) else None,
        sandbox_mode=mode,  # type: ignore[arg-type]
        total_ms=float(harness_ms) if isinstance(harness_ms, (int, float)) and not isinstance(harness_ms, bool) else total_ms,
        errors=errors,
    )


def tail(data: bytes, limit: int = STDERR_TAIL_CHARS) -> str:
    text = data.decode("utf-8", "replace").strip()
    return text if len(text) <= limit else "..." + text[-limit:]


def remove_tree(path: Path, attempts: int = 12) -> bool:
    """Delete a directory tree, retrying while Windows still holds handles of killed processes."""

    def make_writable(func, target, _exc) -> None:
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            func(target)
        except OSError:
            pass

    kwargs = {"onexc": make_writable} if sys.version_info >= (3, 12) else {"onerror": make_writable}
    for attempt in range(attempts):
        try:
            shutil.rmtree(path, **kwargs)
        except OSError:
            pass
        if not os.path.lexists(path):
            return True
        time.sleep(min(0.05 * (attempt + 1), 0.5))
    return not os.path.lexists(path)
