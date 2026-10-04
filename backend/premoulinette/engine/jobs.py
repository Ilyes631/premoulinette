"""In-memory background job manager (analyses, Docker image pulls).

A job function receives a ``progress(stage_key, fraction)`` callback: ``stage_key`` is the stage that
is *starting or running* (earlier stages are then considered done) and ``fraction`` is the overall
progress in ``[0, 1]``. The function returns an optional result id (e.g. the analysis id).

Raising :class:`JobError` fails the job with its message shown verbatim to the user; any other
exception is reported as an unexpected internal error (and logged with its traceback).
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "done", "error"]
StageStatus = Literal["pending", "running", "done", "error"]
ProgressFn = Callable[[str, float], None]
JobFn = Callable[[ProgressFn], "str | None"]


class JobError(Exception):
    """Expected, user-facing failure: the message is displayed as-is."""


class StageState(BaseModel):
    key: str
    label: str
    status: StageStatus = "pending"


class JobState(BaseModel):
    id: str
    kind: str
    status: JobStatus = "queued"
    stage: str | None = None
    stages: list[StageState] = Field(default_factory=list)
    progress: float = 0.0
    result_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class JobManager:
    """Runs jobs on a small thread pool and keeps the state of the most recent ones."""

    def __init__(self, max_workers: int = 2, keep: int = 200) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="premoulinette-job")
        self._jobs: OrderedDict[str, JobState] = OrderedDict()
        self._lock = threading.Lock()
        self._keep = keep

    # ---- public API ---------------------------------------------------------------------------
    def submit(self, kind: str, stages: Sequence[tuple[str, str]], fn: JobFn) -> JobState:
        state = JobState(
            id=uuid.uuid4().hex, kind=kind, stages=[StageState(key=k, label=label) for k, label in stages]
        )
        with self._lock:
            self._jobs[state.id] = state
            self._evict_locked()
            snapshot = state.model_copy(deep=True)
        self._executor.submit(self._run, state.id, fn)
        return snapshot

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            state = self._jobs.get(job_id)
            return state.model_copy(deep=True) if state else None

    def list(self) -> list[JobState]:
        with self._lock:
            return [s.model_copy(deep=True) for s in reversed(self._jobs.values())]

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    # ---- worker side --------------------------------------------------------------------------
    def _run(self, job_id: str, fn: JobFn) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.status = "running"
        try:
            result_id = fn(lambda stage, fraction: self._progress(job_id, stage, fraction))
        except JobError as exc:
            self._finish(job_id, error=str(exc) or "The job failed.")
        except Exception as exc:  # noqa: BLE001 - must never kill the worker thread
            log.exception("Job %s failed unexpectedly", job_id)
            self._finish(job_id, error=f"Unexpected internal error: {type(exc).__name__}: {exc}")
        else:
            self._finish(job_id, result_id=result_id)

    def _progress(self, job_id: str, stage: str, fraction: float) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None or state.status != "running":
                return
            keys = [s.key for s in state.stages]
            if stage in keys:
                idx = keys.index(stage)
                for i, s in enumerate(state.stages):
                    s.status = "done" if i < idx else "running" if i == idx else "pending"
                state.stage = stage
            state.progress = max(state.progress, min(1.0, max(0.0, float(fraction))))

    def _finish(self, job_id: str, *, result_id: str | None = None, error: str | None = None) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.finished_at = datetime.now(timezone.utc)
            if error is None:
                state.status = "done"
                state.result_id = result_id
                state.progress = 1.0
                state.stage = state.stages[-1].key if state.stages else None
                for s in state.stages:
                    s.status = "done"
            else:
                state.status = "error"
                state.error = error
                for s in state.stages:
                    if s.status == "running":
                        s.status = "error"

    def _evict_locked(self) -> None:
        """Drop the oldest *finished* jobs beyond ``keep`` (active jobs are never dropped)."""
        excess = len(self._jobs) - self._keep
        if excess <= 0:
            return
        for job_id in [jid for jid, s in self._jobs.items() if s.status in ("done", "error")][:excess]:
            del self._jobs[job_id]
