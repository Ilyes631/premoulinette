"""Static validation of PracticalSpec (spec editor errors/warnings) and restricted-expression helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from premoulinette.spec.models import (
    BehaviorRule,
    ExerciseSpec,
    FileRequirement,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    Param,
    PracticalSpec,
    ScriptSpec,
    StructureSpec,
)
from premoulinette.spec.validate import (
    is_literal,
    is_safe_relpath,
    parse_restricted_expr,
    restricted_names,
    validate_spec,
)
from premoulinette.subject.extract import extract_document
from premoulinette.subject.heuristic import parse_heuristic

DEMO = Path(__file__).resolve().parents[2] / "demo" / "subject_demo.html"


def _fn(name="f", params=("x",), rules=(), reference=None, tests=()) -> FunctionSpec:
    return FunctionSpec(
        signature=FunctionSignature(name=name, params=[Param(name=p, annotation="int") for p in params]),
        rules=list(rules), reference=reference, tests=list(tests),
    )


def _spec(*exercises: ExerciseSpec, files: list[FileRequirement] | None = None) -> PracticalSpec:
    return PracticalSpec(exercises=list(exercises), structure=StructureSpec(files=files or []))


def _ex(ex_id="e", fns=(), kind="functions", path="e.py", script=None) -> ExerciseSpec:
    return ExerciseSpec(id=ex_id, title=ex_id, kind=kind, file_path=path, functions=list(fns), script=script)


def _levels(issues):
    return [(i.level, i.path) for i in issues]


def test_demo_spec_has_no_issue():
    spec = parse_heuristic(extract_document(DEMO.read_bytes(), DEMO.name)).spec
    assert validate_spec(spec) == []


def test_valid_rules_and_reference():
    fn = _fn(params=("speed", "limit"), rules=[BehaviorRule(when="speed <= limit", returns="True"),
                                               BehaviorRule(when=None, returns="False")],
             tests=[FunctionTest(id="f#ex1", function="f", args=["1", "2"], expected_return="True")])
    assert validate_spec(_spec(_ex(fns=[fn]))) == []
    fn2 = _fn(params=("s",), reference='f"{s // 60:02}:{s % 60:02}"',
              tests=[FunctionTest(id="f#ex1", function="f", args=["61"], expected_return="'01:01'")])
    assert validate_spec(_spec(_ex(fns=[fn2]))) == []


@pytest.mark.parametrize("when", ["speed < 3", "open('x')", "x.__class__", "__import__('os')", "(lambda: 1)()", "x <"])
def test_invalid_conditions_are_errors(when):
    fn = _fn(params=("x",), rules=[BehaviorRule(when=when, returns="1")],
             tests=[FunctionTest(id="f#ex1", function="f", args=["1"], expected_return="1")])
    issues = validate_spec(_spec(_ex(fns=[fn])))
    assert ("error", "exercises[0].functions[0].rules[0].when") in _levels(issues)


def test_reference_with_unknown_name():
    fn = _fn(params=("celsius",), reference="kelvin + 1",
             tests=[FunctionTest(id="f#ex1", function="f", args=["1"], expected_return="2")])
    issues = validate_spec(_spec(_ex(fns=[fn])))
    assert _levels(issues) == [("error", "exercises[0].functions[0].reference")]
    assert "kelvin" in issues[0].message


def test_non_literal_values_and_bad_names():
    fn = _fn(tests=[FunctionTest(id="f#ex1", function="f", args=["x + 1"], kwargs={"1bad": "2", "k": "y"},
                                 expected_return="foo()")])
    paths = _levels(validate_spec(_spec(_ex(fns=[fn]))))
    assert ("error", "exercises[0].functions[0].tests[0].args[0]") in paths
    assert ("error", "exercises[0].functions[0].tests[0].kwargs") in paths
    assert ("error", "exercises[0].functions[0].tests[0].kwargs.k") in paths
    assert ("error", "exercises[0].functions[0].tests[0].expected_return") in paths


def test_test_calling_unknown_function():
    fn = _fn(tests=[FunctionTest(id="g#ex1", function="g", args=["1"], expected_return="1")])
    issues = validate_spec(_spec(_ex(fns=[fn])))
    assert ("error", "exercises[0].functions[0].tests[0].function") in _levels(issues)


def test_unsafe_paths():
    assert is_safe_relpath("a/b.py") is None
    assert is_safe_relpath(".gitignore") is None
    for bad in ("", "/abs.py", "C:/x.py", "a\\b.py", "../x.py", "a/../b.py", "a//b.py", "./a.py"):
        assert is_safe_relpath(bad), bad
    spec = _spec(_ex(path="../evil.py", kind="file"), files=[FileRequirement(path="/etc/passwd")])
    paths = _levels(validate_spec(spec))
    assert ("error", "structure.files[0].path") in paths
    assert ("error", "exercises[0].file_path") in paths


def test_exercise_level_warnings():
    no_test = _ex("a", fns=[_fn()], path="a.py")
    no_fn = _ex("b", kind="functions", path="b.py")
    script_no_session = _ex("c", kind="script", path="c.py", script=ScriptSpec(prompts=["Name: ", ""]))
    issues = validate_spec(_spec(no_test, no_fn, script_no_session))
    assert ("warning", "exercises[0]") in _levels(issues)
    assert ("warning", "exercises[1].functions") in _levels(issues)
    assert ("warning", "exercises[2].script.tests") in _levels(issues)
    assert ("warning", "exercises[2].script.prompts[1]") in _levels(issues)
    assert all(i.level == "warning" for i in issues)


def test_script_kind_without_script_is_error():
    issues = validate_spec(_spec(_ex(kind="script")))
    assert ("error", "exercises[0].script") in _levels(issues)


def test_duplicate_function_and_params():
    sig = FunctionSignature(name="f", params=[Param(name="x"), Param(name="x", default="foo(")])
    fn = FunctionSpec(signature=sig)
    issues = validate_spec(_spec(_ex(fns=[fn, _fn()])))
    paths = _levels(issues)
    assert ("error", "exercises[0].functions") in paths            # f defined twice
    assert ("error", "exercises[0].functions[0].signature.params[1]") in paths
    assert ("error", "exercises[0].functions[0].signature.params[1].default") in paths


def test_helpers():
    assert is_literal("'True'") and is_literal("(1, 2)") and is_literal("-2") and is_literal("{'a': [1]}")
    assert not is_literal("True + x") and not is_literal("print(1)") and not is_literal(None)
    assert restricted_names("2 < vertical_speed <= 5") == {"vertical_speed"}
    assert restricted_names("len(name) > max(a, b)") == {"name", "a", "b"}
    assert restricted_names("__import__('os')") is None
    with pytest.raises(ValueError):
        parse_restricted_expr("")
    with pytest.raises(ValueError):
        parse_restricted_expr("x" * 3000)
