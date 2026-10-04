from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest

from premoulinette.engine.jobs import JobError, JobManager, JobState

STAGES = [("a", "Stage A"), ("b", "Stage B"), ("c", "Stage C")]


@pytest.fixture
def manager() -> Iterator[JobManager]:
    m = JobManager(max_workers=2, keep=200)
    yield m
    m.shutdown(wait=True)


def wait_for(manager: JobManager, job_id: str, statuses: tuple[str, ...] = ("done", "error")) -> JobState:
    deadline = time.monotonic() + 10
    while True:
        state = manager.get(job_id)
        assert state is not None
        if state.status in statuses:
            return state
        assert time.monotonic() < deadline, state
        time.sleep(0.005)


def test_lifecycle(manager: JobManager) -> None:
    started, release, at_b = threading.Event(), threading.Event(), threading.Event()

    def fn(progress):
        started.set()
        progress("a", 0.1)
        progress("b", 0.4)
        at_b.set()
        release.wait(5)
        progress("c", 0.9)
        return "result-42"

    state = manager.submit("analysis", STAGES, fn)
    assert state.status in ("queued", "running")
    assert [s.status for s in state.stages] == ["pending"] * 3
    assert at_b.wait(5)
    running = manager.get(state.id)
    assert running.status == "running"
    assert running.stage == "b"
    assert [s.status for s in running.stages] == ["done", "running", "pending"]
    assert running.progress == pytest.approx(0.4)
    release.set()
    done = wait_for(manager, state.id)
    assert done.status == "done"
    assert done.result_id == "result-42"
    assert done.progress == 1.0
    assert done.error is None
    assert done.finished_at is not None
    assert [s.status for s in done.stages] == ["done"] * 3


def test_progress_is_monotonic_clamped_and_ignores_unknown_stages(manager: JobManager) -> None:
    seen = threading.Event()
    release = threading.Event()

    def fn(progress):
        progress("b", 0.5)
        progress("zzz", 0.2)   # unknown stage: stage unchanged, progress never decreases
        progress("b", 7.0)     # clamped to 1.0
        seen.set()
        release.wait(5)

    state = manager.submit("x", STAGES, fn)
    assert seen.wait(5)
    s = manager.get(state.id)
    assert s.stage == "b"
    assert s.progress == 1.0
    release.set()
    assert wait_for(manager, state.id).result_id is None


def test_user_facing_error(manager: JobManager) -> None:
    def fn(progress):
        progress("b", 0.3)
        raise JobError("Docker is not available. Enable Developer mode in Settings to run locally.")

    state = wait_for(manager, manager.submit("analysis", STAGES, fn).id)
    assert state.status == "error"
    assert state.error == "Docker is not available. Enable Developer mode in Settings to run locally."
    assert [s.status for s in state.stages] == ["done", "error", "pending"]
    assert state.result_id is None


def test_unexpected_error_is_reported_not_raised(manager: JobManager) -> None:
    def fn(progress):
        raise RuntimeError("boom")

    state = wait_for(manager, manager.submit("analysis", STAGES, fn).id)
    assert state.status == "error"
    assert state.error == "Unexpected internal error: RuntimeError: boom"
    # the worker survived: another job still runs
    assert wait_for(manager, manager.submit("x", STAGES, lambda p: "ok").id).result_id == "ok"


def test_get_returns_copies(manager: JobManager) -> None:
    state = wait_for(manager, manager.submit("x", STAGES, lambda p: "r").id)
    state.status = "error"
    state.stages[0].status = "error"
    again = manager.get(state.id)
    assert again.status == "done" and again.stages[0].status == "done"
    assert manager.get("unknown") is None


def test_eviction_keeps_recent_and_active_jobs() -> None:
    m = JobManager(max_workers=1, keep=3)
    try:
        finished = [wait_for(m, m.submit("x", STAGES, lambda p, i=i: str(i)).id).id for i in range(3)]
        gate = threading.Event()
        active = m.submit("slow", STAGES, lambda p: gate.wait(5) and "slow")
        newer = [m.submit("x", STAGES, lambda p: "n").id for _ in range(2)]
        ids = {s.id for s in m.list()}
        assert active.id in ids                      # active jobs are never dropped
        assert finished[0] not in ids and finished[1] not in ids
        gate.set()
        for jid in [active.id, *newer]:
            wait_for(m, jid)
        assert len(m.list()) <= 4
    finally:
        m.shutdown(wait=True)


def test_concurrent_submissions_are_thread_safe(manager: JobManager) -> None:
    ids: list[str] = []
    lock = threading.Lock()

    def submit_many() -> None:
        for _ in range(20):
            s = manager.submit("x", STAGES, lambda p: (p("a", 0.5), "ok")[1])
            with lock:
                ids.append(s.id)

    threads = [threading.Thread(target=submit_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 80
    assert all(wait_for(manager, jid).status == "done" for jid in ids)
