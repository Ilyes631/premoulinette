"""Harness-level tests: run_plan.py driven directly (no sandbox wrapper) + its pure helpers."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from premoulinette.runner.models import RunResults
from premoulinette.sandbox import common

RUN_PLAN = common.HARNESS_DIR / "run_plan.py"
CHILD = common.HARNESS_DIR / "child.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_plan = _load("_pm_test_run_plan", RUN_PLAN)


def _harness(plan: dict | str, root: Path, tmp: Path) -> tuple[int, str]:
    plan_file = tmp / "plan.json"
    plan_file.write_text(plan if isinstance(plan, str) else json.dumps(plan), encoding="utf-8")
    env = {"PATH": os.path.dirname(sys.executable), "TEMP": str(tmp), "TMP": str(tmp)}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    proc = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", str(RUN_PLAN), str(plan_file), "--root", str(root)],
        capture_output=True, timeout=60, env=env, cwd=str(root),
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / "sub").mkdir(parents=True)
    (project / "mod.py").write_text(
        "import os\n\ndef add(a, b=0):\n    return a + b\n\ndef cwd():\n    return os.getcwd()\n", encoding="utf-8"
    )
    (project / "sub" / "argv.py").write_text(
        "import sys\n\ndef f(a: int):\n    pass\n\nprint(sys.argv)\nprint(__name__, f.__annotations__['a'] is int, sys.modules['__main__'].__file__ == __file__)\n",
        encoding="utf-8",
    )
    (project / "bad.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    return project


def test_markers_match_the_backend():
    assert run_plan.BEGIN_MARKER == common.BEGIN_MARKER
    assert run_plan.END_MARKER == common.END_MARKER
    assert run_plan.MAX_PARALLEL == common.HARNESS_MAX_PARALLEL
    assert run_plan.KILL_GRACE_S == common.HARNESS_KILL_GRACE_S


def test_harness_is_stdlib_only():
    for path in (RUN_PLAN, CHILD):
        text = path.read_text(encoding="utf-8")
        assert "premoulinette." not in text.replace("premoulinette.runner.models", "")
        assert "import pydantic" not in text and "from pydantic" not in text


def test_run_plan_end_to_end(root: Path, tmp_path: Path):
    plan = {
        "jobs": [
            {"kind": "function", "id": "kw", "module_path": "mod.py", "function": "add", "args": ["1"], "kwargs": {"b": "2"}},
            {"kind": "function", "id": "badarg", "module_path": "mod.py", "function": "add", "args": ["os.system('x')"]},
            {"kind": "function", "id": "nofn", "module_path": "mod.py", "function": "nope"},
            {"kind": "function", "id": "missing", "module_path": "nothere.py", "function": "f"},
            {"kind": "function", "id": "abs", "module_path": str(root / "mod.py"), "function": "add"},
            {"kind": "import", "id": "syntax", "module_path": "bad.py"},
            {"kind": "script", "id": "argv", "script_path": "sub/argv.py", "argv": ["a b", "é"]},
            {"kind": "weird", "id": "weird"},
        ],
        "max_parallel": 3,
    }
    code, out = _harness(plan, root, tmp_path)
    assert code == 0
    payload, problem = common.extract_payload(out), None
    assert payload is not None, problem
    results = RunResults.model_validate(json.loads(payload))
    by_id = {r.id: r for r in results.results}
    assert [r.id for r in results.results] == [j["id"] for j in plan["jobs"]]
    assert (by_id["kw"].status, by_id["kw"].return_repr) == ("ok", "3")
    assert by_id["badarg"].status == "harness_error" and "literal" in (by_id["badarg"].harness_error or "")
    assert by_id["nofn"].status == "exception" and by_id["nofn"].exception.type == "AttributeError"
    assert by_id["missing"].status == "harness_error" and "not found" in by_id["missing"].harness_error
    assert by_id["abs"].status == "harness_error" and "absolute" in by_id["abs"].harness_error
    syntax = by_id["syntax"]
    assert syntax.status == "syntax_error"
    assert syntax.exception.type == "SyntaxError" and syntax.exception.file == "bad.py" and syntax.exception.line == 1
    argv = by_id["argv"]
    assert argv.status == "ok" and argv.stdout == "['argv.py', 'a b', 'é']\n__main__ True True\n"
    assert by_id["weird"].status == "harness_error"


def test_invalid_plan_still_emits_markers(root: Path, tmp_path: Path):
    code, out = _harness("{not json", root, tmp_path)
    assert code == 2
    data = json.loads(common.extract_payload(out))
    assert data["results"] == [] and "invalid run plan" in data["errors"][0]


def test_sanitize_child_rejects_hostile_fields():
    hostile = {
        "status": "pwned", "duration_ms": "fast", "return_repr": 5, "return_literal": "yes",
        "events": [{"kind": "output", "text": "ok", "file": 3, "line": "2"}, {"kind": "evil", "text": "x"}, "junk"],
        "blocked_syscalls": ["socket.connect", 7], "exception": {"type": None, "message": "m\ud800"},
        "exit_code": True,
    }
    clean = run_plan.sanitize_child(hostile)
    assert clean["status"] == "harness_error"
    assert clean["duration_ms"] == 0.0 and clean["return_repr"] is None and clean["return_literal"] is False
    assert clean["events"] == [{"kind": "output", "text": "ok", "file": None, "line": None}]
    assert clean["blocked_syscalls"] == ["socket.connect"]
    assert clean["exception"]["type"] == "Exception" and clean["exception"]["message"].encode("utf-8")
    assert clean["exit_code"] is None


def test_merge_result_parent_observations_win():
    job = {"kind": "script", "id": "s", "timeout_s": 1.0}
    cap = run_plan.Capture()
    cap.stdout, cap.stderr, cap.timed_out = b"partial", b"", True
    merged = run_plan.merge_result(job, cap, {"status": "ok", "stdout": "forged", "exit_code": 0})
    assert merged["status"] == "timeout" and merged["exit_code"] is None and merged["stdout"] == "partial"
    cap2 = run_plan.Capture()
    cap2.returncode = 3
    crashed = run_plan.merge_result({"kind": "function", "id": "f", "timeout_s": 1.0}, cap2, None)
    assert crashed["status"] == "crash" and "without reporting" in crashed["harness_error"]


def test_resolve_inside_rejects_escapes(tmp_path: Path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    assert run_plan.resolve_inside(str(tmp_path), "a.py")[0] is not None
    for bad in ("../a.py", "/etc/passwd", "", "x\x00.py", None, "C:/Windows/win.ini" if os.name == "nt" else "/x"):
        target, problem = run_plan.resolve_inside(str(tmp_path), bad)
        assert target is None and problem
