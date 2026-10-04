from __future__ import annotations

from premoulinette.engine.planning import build_run_plan, effective_timeout, file_blockers
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo, SyntaxErrorInfo
from premoulinette.runner.models import FunctionJob, ImportJob, ScriptJob
from premoulinette.spec.models import (
    ExerciseSpec,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
)
from test_api_fakes import FakeGeneratedFunctionTest, FakeGeneratedScriptTest, fake_generate_tests, make_spec


def module(path: str, *functions: str, ok: bool = True) -> ModuleInfo:
    return ModuleInfo(
        path=path, ok=ok, syntax_error=None if ok else SyntaxErrorInfo(message="expected ':'", line=1),
        functions=[FunctionInfo(name=f, line=1, end_line=2) for f in functions],
    )


def test_file_blockers() -> None:
    spec = make_spec()
    modules = {"pkg/safe_speed.py": module("pkg/safe_speed.py", "is_safe"), "x/hello.py": module("x/hello.py", ok=False)}
    file_map = {"pkg/safe_speed.py": "pkg/safe_speed.py", "pkg/hello.py": "x/hello.py", "pkg/absent.py": None}
    assert file_blockers(spec, modules, file_map) == {
        "pkg/hello.py": "syntax:pkg/hello.py",
        "pkg/absent.py": "structure:file:pkg/absent.py",
    }


def test_plan_uses_snapshot_paths_and_records_blockers() -> None:
    spec = make_spec()
    fn_tests, script_tests = fake_generate_tests(spec)
    modules = {
        "root/pkg/safe_speed.py": module("root/pkg/safe_speed.py", "is_safe"),
        "root/misplaced/hello.py": module("root/misplaced/hello.py"),
    }
    file_map = {
        "pkg/safe_speed.py": "root/pkg/safe_speed.py",
        "pkg/hello.py": "root/misplaced/hello.py",     # misplaced: tests still run on the found file
        "pkg/absent.py": None,
    }
    planned = build_run_plan(spec, fn_tests, script_tests, modules, file_map, default_timeout_s=3.0)
    jobs = {j.id: j for j in planned.plan.jobs}

    assert isinstance(jobs["import:safe_speed"], ImportJob)
    assert jobs["import:safe_speed"].module_path == "root/pkg/safe_speed.py"
    assert planned.import_jobs == {"import:safe_speed": "safe_speed"}
    fn = jobs["is_safe#ex1"]
    assert isinstance(fn, FunctionJob)
    assert (fn.module_path, fn.function, fn.args, fn.timeout_s) == ("root/pkg/safe_speed.py", "is_safe", ["200", "250"], 3.0)
    assert "is_safe#derived1" in jobs
    script = jobs["hello#session1"]
    assert isinstance(script, ScriptJob)
    assert (script.script_path, script.stdin) == ("root/misplaced/hello.py", "Bob\n")
    assert "f#ex1" not in jobs
    assert planned.blocked_tests == {"f#ex1": "structure:file:pkg/absent.py"}
    assert planned.blocked_files == {"pkg/absent.py": "structure:file:pkg/absent.py"}
    assert planned.warnings == []


def test_missing_function_and_syntax_error_block_tests() -> None:
    spec = make_spec()
    fn_tests, script_tests = fake_generate_tests(spec)
    modules = {
        "pkg/safe_speed.py": module("pkg/safe_speed.py", "is_safe_typo"),
        "pkg/hello.py": module("pkg/hello.py", ok=False),
        "pkg/absent.py": module("pkg/absent.py", "f"),
    }
    file_map = {p: p for p in ("pkg/safe_speed.py", "pkg/hello.py", "pkg/absent.py")}
    planned = build_run_plan(spec, fn_tests, script_tests, modules, file_map, default_timeout_s=5.0)
    assert planned.blocked_tests == {
        "is_safe#ex1": "function:safe_speed:is_safe",
        "is_safe#ex2": "function:safe_speed:is_safe",
        "is_safe#derived1": "function:safe_speed:is_safe",
        "hello#session1": "syntax:pkg/hello.py",
    }
    ids = [j.id for j in planned.plan.jobs]
    assert ids == ["import:safe_speed", "import:absent", "f#ex1"]


def test_shared_file_gets_one_import_job_owned_by_the_mandatory_exercise() -> None:
    def fn_ex(ex_id: str, fn: str, bonus: bool) -> ExerciseSpec:
        return ExerciseSpec(
            id=ex_id, title=ex_id, file_path="grade.py", bonus=bonus,
            functions=[FunctionSpec(signature=FunctionSignature(name=fn),
                                    tests=[FunctionTest(id=f"{fn}#ex1", function=fn, args=["1"])])],
        )

    spec = PracticalSpec(exercises=[fn_ex("emoji_grade", "emoji", True), fn_ex("grade_landing", "landing", False)])
    modules = {"grade.py": module("grade.py", "landing")}
    fn_tests = [FakeGeneratedFunctionTest(test=t, exercise_id=e.id, category="explicit_tests") for e, _, t in spec.all_function_tests()]
    planned = build_run_plan(spec, fn_tests, [], modules, {"grade.py": "grade.py"}, default_timeout_s=5.0)
    assert planned.import_jobs == {"import:grade_landing": "grade_landing"}
    assert planned.blocked_tests == {"emoji#ex1": "function:emoji_grade:emoji"}


def test_duplicate_ids_and_unknown_exercises_are_reported() -> None:
    spec = PracticalSpec(exercises=[ExerciseSpec(
        id="s", title="s", kind="script", file_path="s.py",
        script=ScriptSpec(tests=[ScriptTest(id="s#session1")]),
    )])
    test = ScriptTest(id="s#session1")
    scripts = [
        FakeGeneratedScriptTest(test=test, exercise_id="s"),
        FakeGeneratedScriptTest(test=test, exercise_id="s"),
        FakeGeneratedScriptTest(test=ScriptTest(id="z#session1"), exercise_id="zzz"),
    ]
    planned = build_run_plan(spec, [], scripts, {"s.py": module("s.py")}, {"s.py": "s.py"}, default_timeout_s=5.0)
    assert [j.id for j in planned.plan.jobs] == ["s#session1"]
    assert len(planned.warnings) == 2


def test_effective_timeout() -> None:
    assert effective_timeout(5.0, 2.0) == 2.0      # spec default defers to the settings
    assert effective_timeout(12.0, 2.0) == 12.0    # explicit value wins
    assert effective_timeout(5.0, 600.0) == 60.0   # bounded
