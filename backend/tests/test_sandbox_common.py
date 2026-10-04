"""Result parsing, budgets and Windows Job Object helpers."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from premoulinette.runner.models import FunctionJob, RunPlan, ScriptJob
from premoulinette.sandbox import common
from premoulinette.sandbox.base import copy_project

PLAN = RunPlan(
    jobs=[FunctionJob(id="f1", module_path="m.py", function="f"), ScriptJob(id="s1", script_path="s.py")],
    max_parallel=2,
)


def _wrap(payload: dict) -> str:
    return f"noise\n{common.BEGIN_MARKER}\n{json.dumps(payload)}\n{common.END_MARKER}\n"


def test_missing_markers_mark_every_job_as_harness_error():
    results = common.parse_results("Traceback: boom", PLAN, "local", process_error="exit 1")
    assert [(r.id, r.kind, r.status) for r in results.results] == [
        ("f1", "function", "harness_error"), ("s1", "script", "harness_error"),
    ]
    assert all(r.harness_error for r in results.results)
    assert results.errors and "exit 1" in results.errors[0]


def test_truncated_or_invalid_payload():
    assert common.parse_results(common.BEGIN_MARKER + "{}", PLAN, "local").results[0].status == "harness_error"
    bad = common.parse_results(f"{common.BEGIN_MARKER}\nnot json\n{common.END_MARKER}", PLAN, "local")
    assert all(r.status == "harness_error" for r in bad.results)


def test_partial_results_are_completed():
    payload = {
        "results": [{"id": "f1", "kind": "function", "status": "ok", "return_repr": "1", "return_type": "int"},
                    {"id": "zz", "kind": "function", "status": "bogus"}],
        "python_version": "3.12.4", "total_ms": 12.5, "errors": [],
    }
    results = common.parse_results(_wrap(payload), PLAN, "docker")
    by_id = {r.id: r for r in results.results}
    assert by_id["f1"].status == "ok" and by_id["f1"].return_repr == "1"
    assert by_id["s1"].status == "harness_error"
    assert results.python_version == "3.12.4" and results.sandbox_mode == "docker"
    assert any("invalid result" in e for e in results.errors)


def test_global_timeout_covers_the_longest_job():
    plan = RunPlan(jobs=[FunctionJob(id="long", module_path="m.py", function="f", timeout_s=30)], max_parallel=4)
    assert common.global_timeout(plan, 15) >= 30 + 15
    many = RunPlan(jobs=[FunctionJob(id=str(i), module_path="m.py", function="f", timeout_s=5) for i in range(8)],
                   max_parallel=4)
    assert common.global_timeout(many, 15) >= 8 * 5 / 4 + 15


def test_copy_project_skips_git_and_pycache(tmp_path: Path):
    src = tmp_path / "src"
    (src / ".git" / "hooks").mkdir(parents=True)
    (src / "pkg" / "__pycache__").mkdir(parents=True)
    (src / "pkg" / "__pycache__" / "x.cpython-314.pyc").write_bytes(b"\0")
    (src / "pkg" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (src / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    dest = tmp_path / "dest"
    copy_project(src, dest)
    assert (dest / "pkg" / "x.py").is_file() and (dest / ".gitignore").is_file()
    assert not (dest / ".git").exists() and not (dest / "pkg" / "__pycache__").exists()


def test_remove_tree(tmp_path: Path):
    target = tmp_path / "t"
    (target / "a").mkdir(parents=True)
    ro = target / "a" / "ro.txt"
    ro.write_text("x", encoding="utf-8")
    os.chmod(ro, 0o444)
    assert common.remove_tree(target) is True and not target.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects")
def test_winjob_kills_the_whole_job():
    from premoulinette.sandbox import winjob

    python = getattr(sys, "_base_executable", None) or sys.executable  # no venv launcher process in between
    proc = subprocess.Popen([python, "-c", "import time; time.sleep(60)"],
                            creationflags=subprocess.CREATE_NO_WINDOW)
    job = winjob.create_job(max_processes=4, memory_bytes=256 * 1024 * 1024)
    try:
        winjob.assign(job, int(proc._handle))
        start = time.perf_counter()
        assert winjob.terminate(job) is True
        assert proc.wait(timeout=10) is not None
        assert time.perf_counter() - start < 5
    finally:
        winjob.close(job)
        if proc.poll() is None:
            proc.kill()
