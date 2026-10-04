"""languages/python/checks_static.py — syntax, functions, constraints and import side-effect checks."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from conftest import DEMO_DIR
from premoulinette.languages.python.checks_static import (
    check_constraints,
    check_functions,
    check_import_side_effects,
    check_syntax,
)
from premoulinette.languages.python.static import analyze_project, analyze_source
from premoulinette.spec.models import (
    BehaviorRule,
    Constraints,
    ExerciseSpec,
    FileRequirement,
    FunctionSignature,
    FunctionSpec,
    Param,
    PracticalSpec,
    StructureSpec,
)

# ---- builders ------------------------------------------------------------------------------------


def fn(name: str, params: str = "", ret: str | None = None, **kw) -> FunctionSpec:
    ps = []
    for p in filter(None, (x.strip() for x in params.split(","))):
        n, _, ann = p.partition(":")
        ps.append(Param(name=n.strip(), annotation=ann.strip() or None))
    return FunctionSpec(signature=FunctionSignature(name=name, params=ps, return_annotation=ret), **kw)


def ex(eid: str, path: str, *functions: FunctionSpec, **kw) -> ExerciseSpec:
    kind = kw.pop("kind", "functions" if functions else "script")
    return ExerciseSpec(id=eid, title=eid, kind=kind, file_path=path, functions=list(functions), **kw)


def spec_of(*exercises: ExerciseSpec, constraints: Constraints | None = None) -> PracticalSpec:
    return PracticalSpec(exercises=list(exercises), global_constraints=constraints or Constraints())


def by_id(checks) -> dict:
    ids = [c.id for c in checks]
    assert len(ids) == len(set(ids)), f"duplicate check ids: {ids}"
    return {c.id: c for c in checks}


# ---- syntax ---------------------------------------------------------------------------------------


def test_syntax_error_check_has_location_and_excerpt():
    spec = spec_of(ex("speed", "ex/speed.py", fn("average_speed", "d, h", "float")))
    mods = {"ex/speed.py": analyze_source("def average_speed(d, h):\n    if h == 0\n        return 0.0\n    return d / h\n",
                                          "ex/speed.py")}
    (c,) = check_syntax(mods, {"ex/speed.py": "ex/speed.py"}, spec)
    assert (c.id, c.status, c.severity, c.diagnosis, c.mandatory) == ("syntax:ex/speed.py", "fail", "critical", "syntax_error", True)
    assert (c.location.file, c.location.line, c.location.col) == ("ex/speed.py", 2, 13)   # 0-based, after the ':'-less line
    assert "line 2" in c.message and "expected ':'" in c.message
    code = c.evidence.code
    assert code.start_line == 1 and code.highlight == [2] and code.lines[1] == "    if h == 0"
    # function checks on a broken file are skipped and point to the syntax check
    (f,) = check_functions(spec, mods, {"ex/speed.py": "ex/speed.py"})
    assert (f.status, f.blocked_by, f.mandatory) == ("skipped", "syntax:ex/speed.py", True)


def test_syntax_pass_indentation_and_misplaced_paths():
    spec = spec_of(ex("a", "A/a.py", fn("f")), ex("b", "A/b.py", fn("g")))
    mods = {"wrong/a.py": analyze_source("def f():\n    return 1\n", "wrong/a.py"),
            "A/b.py": analyze_source("def g():\n  x = 1\n    return x\n", "A/b.py"),
            "extra.py": analyze_source("def (:\n", "extra.py")}
    checks = by_id(check_syntax(mods, {"A/a.py": "wrong/a.py", "A/b.py": "A/b.py"}, spec))
    a = checks["syntax:A/a.py"]
    assert a.status == "pass" and a.file == "A/a.py" and a.location.file == "wrong/a.py"
    b = checks["syntax:A/b.py"]
    assert (b.status, b.diagnosis, b.location.line) == ("fail", "indentation_error", 3)
    extra = checks["syntax:extra.py"]
    assert extra.status == "info" and not extra.mandatory


def test_encoding_error_check(tmp_path: Path):
    (tmp_path / "a.py").write_bytes(b"s = '\xe9'\n")
    mods = analyze_project(tmp_path, ["a.py"])
    spec = spec_of(ex("a", "a.py", fn("f")))
    (c,) = check_syntax(mods, {"a.py": "a.py"}, spec)
    assert (c.status, c.diagnosis) == ("fail", "encoding_error")


def test_bonus_file_syntax_error_is_bonus_status():
    spec = spec_of(ex("b", "bonus/b.py", fn("f"), bonus=True))
    mods = {"bonus/b.py": analyze_source("def f(:\n", "bonus/b.py")}
    (c,) = check_syntax(mods, {"bonus/b.py": "bonus/b.py"}, spec)
    assert (c.status, c.mandatory, c.bonus) == ("bonus", False, True)


# ---- functions ------------------------------------------------------------------------------------


def test_function_presence_signature_and_returns_pass():
    spec = spec_of(ex("safe", "safe.py", fn("is_safe", "speed: int, limit: int", "bool")))
    mods = {"safe.py": analyze_source(
        "def is_safe(speed: int, limit: int) -> bool:\n    return speed <= limit\n", "safe.py")}
    checks = by_id(check_functions(spec, mods, {"safe.py": "safe.py"}))
    assert {k: c.status for k, c in checks.items()} == {
        "function:safe:is_safe": "pass", "signature:safe:is_safe": "pass", "returns:safe:is_safe": "pass"}
    assert checks["function:safe:is_safe"].location.line == 1
    assert all(c.file == "safe.py" and c.exercise_id == "safe" and c.function == "is_safe" for c in checks.values())


def test_near_miss_function_name():
    spec = spec_of(ex("safe", "safe.py", fn("is_safe", "speed, limit", "bool")))
    mods = {"safe.py": analyze_source("# x\ndef is_save(speed, limit):\n    return speed <= limit\n", "safe.py")}
    (c,) = check_functions(spec, mods, {"safe.py": "safe.py"})
    assert (c.id, c.status, c.severity, c.diagnosis) == ("function:safe:is_safe", "fail", "critical", "wrong_function_name")
    assert "Found def is_save()" in c.message and "did you mean is_safe()?" in c.message
    assert (c.location.file, c.location.line) == ("safe.py", 2)
    assert c.evidence.details["found"] == "is_save"
    assert c.evidence.code.highlight == [2]


def test_missing_function_and_function_in_wrong_file():
    spec = spec_of(ex("k", "k.py", fn("to_kelvin", "c", "float"), fn("to_celsius", "k", "float")))
    mods = {"k.py": analyze_source("def unrelated():\n    return 1\n", "k.py"),
            "other.py": analyze_source("\n\ndef to_celsius(k):\n    return k - 273.15\n", "other.py")}
    checks = by_id(check_functions(spec, mods, {"k.py": "k.py"}))
    missing = checks["function:k:to_kelvin"]
    assert (missing.status, missing.severity, missing.diagnosis) == ("fail", "critical", "missing_function")
    assert "to_kelvin()" in missing.message and "k.py" in missing.message
    wrong = checks["function:k:to_celsius"]
    assert (wrong.status, wrong.diagnosis) == ("fail", "function_in_wrong_file")
    assert (wrong.location.file, wrong.location.line) == ("other.py", 3) and wrong.file == "k.py"
    assert "other.py" in wrong.message


def test_missing_file_skips_or_marks_bonus():
    spec = spec_of(ex("a", "a.py", fn("f")), ex("b", "b.py", fn("g"), bonus=True))
    checks = by_id(check_functions(spec, {}, {"a.py": None, "b.py": None}))
    a, b = checks["function:a:f"], checks["function:b:g"]
    assert (a.status, a.blocked_by, a.mandatory) == ("skipped", "structure:file:a.py", True)
    assert (b.status, b.diagnosis, b.mandatory, b.bonus) == ("bonus", "bonus_not_implemented", False, True)


def test_nested_function_is_reported():
    spec = spec_of(ex("a", "a.py", fn("f", "x", "int")))
    mods = {"a.py": analyze_source("def main():\n    def f(x):\n        return x\n    return f(1)\n", "a.py")}
    (c,) = check_functions(spec, mods, {"a.py": "a.py"})
    assert (c.status, c.diagnosis, c.location.line) == ("fail", "nested_function", 2)


@pytest.mark.parametrize(
    ("code", "status", "severity", "diagnosis"),
    [
        ("def f(a, b, c):\n    return a\n", "fail", "critical", "wrong_param_count"),
        ("def f(a):\n    return a\n", "fail", "critical", "wrong_param_count"),
        ("def f(a: int, b: int, *, c):\n    return a\n", "fail", "critical", "wrong_param_count"),
        ("def f(a: int, b: int, c=0) -> int:\n    return a\n", "pass", None, None),
        ("def f(a: int, *rest) -> int:\n    return a\n", "pass", None, None),
        ("def f(x: int, y: int) -> int:\n    return x\n", "fail", "minor", "wrong_param_names"),
        ("def f(a, b):\n    return a\n", "warning", "style", "wrong_annotation"),
        ("def f(a: int, b: int) -> str:\n    return a\n", "warning", "style", "wrong_annotation"),
    ],
)
def test_signature_rules(code, status, severity, diagnosis):
    spec = spec_of(ex("e", "e.py", fn("f", "a: int, b: int", "int")))
    mods = {"e.py": analyze_source(code, "e.py")}
    c = by_id(check_functions(spec, mods, {"e.py": "e.py"}))["signature:e:f"]
    assert (c.status, c.severity, c.diagnosis) == (status, severity, diagnosis)
    assert c.evidence.code is not None and c.evidence.details["expected_signature"] == "def f(a: int, b: int) -> int"


def test_str_instead_of_bool_points_to_the_return_line():
    spec = spec_of(ex("safe", "safe.py", fn("is_safe", "speed: int, limit: int", "bool")))
    code = 'def is_safe(speed: int, limit: int) -> bool:\n    if speed <= limit:\n        return "True"\n    else:\n        return "False"\n'
    mods = {"safe.py": analyze_source(code, "safe.py")}
    c = by_id(check_functions(spec, mods, {"safe.py": "safe.py"}))["returns:safe:is_safe"]
    assert (c.status, c.severity, c.diagnosis) == ("fail", "major", "str_instead_of_bool")
    assert c.location.line == 3 and c.evidence.details["lines"] == [3, 5]
    assert c.evidence.code.highlight == [3, 5]
    assert 'return "True"' in c.message


def test_prints_instead_of_returns_and_returns_none():
    spec = spec_of(ex("clock", "clock.py", fn("mission_clock", "seconds: int", "str"), fn("stub", "", "int")))
    code = 'def mission_clock(seconds: int) -> str:\n    h = seconds // 3600\n    print(f"{h:02}")\n\ndef stub() -> int:\n    pass\n'
    mods = {"clock.py": analyze_source(code, "clock.py")}
    checks = by_id(check_functions(spec, mods, {"clock.py": "clock.py"}))
    c = checks["returns:clock:mission_clock"]
    assert (c.status, c.severity, c.diagnosis, c.location.line) == ("fail", "major", "prints_instead_of_returns", 3)
    s = checks["returns:clock:stub"]
    assert (s.status, s.diagnosis) == ("warning", "returns_none")


def test_printing_function_without_return_value_in_subject_is_not_flagged():
    spec = spec_of(ex("show", "show.py", fn("show", "x")))   # no return annotation, no expected value
    mods = {"show.py": analyze_source("def show(x):\n    print(x)\n", "show.py")}
    checks = by_id(check_functions(spec, mods, {"show.py": "show.py"}))
    assert "returns:show:show" not in checks


def test_bonus_function_failures_are_bonus_status():
    spec = spec_of(ex("main", "g.py", fn("landing_grade", "v: int", "str")),
                   ex("emoji", "g.py", fn("emoji_grade", "v: int", "str"), fn("other", "", "str"), bonus=True))
    mods = {"g.py": analyze_source('def landing_grade(v: int) -> str:\n    return "x"\n\ndef other() -> str:\n    print(1)\n', "g.py")}
    checks = by_id(check_functions(spec, mods, {"g.py": "g.py"}))
    missing = checks["function:emoji:emoji_grade"]
    assert (missing.status, missing.diagnosis, missing.mandatory, missing.bonus) == ("bonus", "bonus_not_implemented", False, True)
    printing = checks["returns:emoji:other"]
    assert (printing.status, printing.mandatory, printing.bonus) == ("bonus", False, True)
    assert checks["function:main:landing_grade"].mandatory is True


# ---- constraints ----------------------------------------------------------------------------------

DEMO_CONSTRAINTS = Constraints(allowed_builtins=["input", "print", "len", "int", "str", "float", "bool"],
                               forbidden_builtins=["abs", "max", "min", "round", "sorted", "sum", "eval"],
                               allowed_imports=[])


def run_constraints(code: str, constraints: Constraints = DEMO_CONSTRAINTS, *, bonus: bool = False):
    spec = spec_of(ex("e", "e.py", fn("f", "x"), bonus=bonus), constraints=constraints)
    mods = {"e.py": analyze_source(textwrap.dedent(code).lstrip("\n"), "e.py")}
    return by_id(check_constraints(spec, mods, {"e.py": "e.py"}))


def test_clean_file_gets_one_pass_per_active_family():
    checks = run_constraints("def f(x):\n    return len(str(x))\n")
    assert {k: c.status for k, c in checks.items()} == {
        "constraint:e:forbidden_builtin:*": "pass", "constraint:e:builtin_not_allowed:*": "pass",
        "constraint:e:import:*": "pass"}
    assert all(c.category == "constraints" and c.mandatory for c in checks.values())


def test_forbidden_builtin_one_check_per_builtin_with_all_lines():
    checks = run_constraints("""
        def f(x):
            a = round(x)
            b = round(x / 2)
            return max(a, b)
    """)
    r = checks["constraint:e:forbidden_builtin:round"]
    assert (r.status, r.severity, r.diagnosis) == ("fail", "critical", "forbidden_builtin")
    assert r.location.line == 2 and r.evidence.details["lines"] == [2, 3]
    assert r.evidence.code.highlight == [2, 3]
    assert "round()" in r.message and "f()" in r.message
    assert checks["constraint:e:forbidden_builtin:max"].location.line == 4
    assert "constraint:e:forbidden_builtin:*" not in checks
    assert "constraint:e:builtin_not_allowed:max" not in checks   # reported once, as forbidden


def test_shadowed_builtin_is_not_flagged():
    checks = run_constraints("""
        def max(a, b):
            if a > b:
                return a
            return b
        def f(x):
            return max(x, 0)
    """)
    assert checks["constraint:e:forbidden_builtin:*"].status == "pass"


def test_builtin_not_allowed_and_exceptions_ignored():
    checks = run_constraints("""
        def f(x):
            if x < 0:
                raise ValueError("negative")
            for i in range(x):
                print(i)
            return isinstance(x, int)
    """)
    assert checks["constraint:e:builtin_not_allowed:range"].diagnosis == "builtin_not_allowed"
    assert checks["constraint:e:builtin_not_allowed:isinstance"].status == "fail"
    assert "constraint:e:builtin_not_allowed:ValueError" not in checks
    assert "range()" in checks["constraint:e:builtin_not_allowed:range"].message


def test_referenced_forbidden_builtin_is_a_bypass():
    checks = run_constraints("""
        def f(xs):
            g = abs
            return g(xs[0])
    """)
    c = checks["constraint:e:builtin_bypass:abs"]
    assert (c.status, c.severity, c.diagnosis, c.location.line) == ("fail", "critical", "builtin_bypass", 2)


@pytest.mark.parametrize("code,key", [
    ("def f(x):\n    return __builtins__.abs(x)\n", "__builtins__"),
    ("import builtins\ndef f(x):\n    return getattr(builtins, 'abs')(x)\n", "builtins"),
    ("def f(x):\n    return __import__('math').fabs(x)\n", "__import__"),
])
def test_bypasses(code, key):
    checks = run_constraints(code, Constraints(forbidden_builtins=["abs"]))
    assert checks[f"constraint:e:builtin_bypass:{key}"].diagnosis == "builtin_bypass"


def test_eval_forbidden_reported_once_not_as_bypass():
    checks = run_constraints("def f(x):\n    return eval(x)\n")
    assert checks["constraint:e:forbidden_builtin:eval"].status == "fail"
    assert "constraint:e:builtin_bypass:eval" not in checks


def test_imports_when_none_allowed_and_forbidden_imports():
    checks = run_constraints("import math\nfrom os import path\ndef f(x):\n    return math.floor(x)\n")
    m = checks["constraint:e:import:math"]
    assert (m.status, m.severity, m.diagnosis, m.location.line) == ("fail", "critical", "forbidden_import", 1)
    assert "forbids every import" in m.message
    assert checks["constraint:e:import:os"].evidence.details["statement"] == "from os import path"
    allowed = run_constraints("import math\nimport os.path\nimport random\n",
                              Constraints(allowed_imports=["math", "os"], forbidden_imports=["random"]))
    assert set(allowed) == {"constraint:e:import:random"}


def test_methods_and_constructs():
    cons = Constraints(forbidden_methods=["sort"], forbidden_constructs=["loop", "lambda"],
                       required_constructs=["recursion"])
    checks = run_constraints("""
        def f(xs):
            xs.sort()
            for x in xs:
                pass
            return sorted(xs, key=lambda v: v)
    """, cons)
    assert checks["constraint:e:method:sort"].diagnosis == "forbidden_method"
    loop = checks["constraint:e:construct:loop"]
    assert (loop.diagnosis, loop.location.line) == ("forbidden_construct", 3)
    assert checks["constraint:e:construct:lambda"].location.line == 5
    rec = checks["constraint:e:required_construct:recursion"]
    assert (rec.status, rec.severity, rec.diagnosis) == ("fail", "major", "missing_required_construct")
    ok = run_constraints("def f(n):\n    return 1 if n == 0 else n * f(n - 1)\n", cons)
    assert ok["constraint:e:required_construct:recursion"].status == "pass"
    assert ok["constraint:e:method:*"].status == "pass" and ok["constraint:e:construct:*"].status == "pass"


def test_bonus_constraint_failure_has_bonus_status():
    checks = run_constraints("def f(x):\n    return abs(x)\n", bonus=True)
    c = checks["constraint:e:forbidden_builtin:abs"]
    assert (c.status, c.mandatory, c.bonus, c.severity) == ("bonus", False, True, "critical")


def test_shared_file_attributes_uses_to_the_owning_exercise():
    spec = spec_of(ex("main", "g.py", fn("landing_grade", "v")), ex("emoji", "g.py", fn("emoji_grade", "v"), bonus=True),
                   constraints=Constraints(forbidden_builtins=["max"]))
    code = "def landing_grade(v):\n    return v\n\ndef emoji_grade(v):\n    return max(v, 0)\n"
    checks = by_id(check_constraints(spec, {"g.py": analyze_source(code, "g.py")}, {"g.py": "g.py"}))
    assert checks["constraint:main:forbidden_builtin:*"].status == "pass"
    assert checks["constraint:emoji:forbidden_builtin:max"].status == "bonus"


# ---- import side effects --------------------------------------------------------------------------


def test_import_side_effects_warning_and_main_guard():
    spec = spec_of(ex("k", "k.py", fn("to_kelvin", "c", "float")), ex("s", "s.py", fn("g")),
                   ex("script", "script.py", kind="script"))
    mods = {
        "k.py": analyze_source("def to_kelvin(c):\n    return c + 273.15\n\n\nprint(to_kelvin(25))\n", "k.py"),
        "s.py": analyze_source("def g():\n    return 1\n\nif __name__ == '__main__':\n    print(g())\n", "s.py"),
        "script.py": analyze_source("print(input('x'))\n", "script.py"),
    }
    checks = by_id(check_import_side_effects(spec, mods, {"k.py": "k.py", "s.py": "s.py", "script.py": "script.py"}))
    k = checks["import_effects:k"]
    assert (k.status, k.severity, k.mandatory, k.diagnosis, k.category) == ("warning", "major", True, "import_side_effects", "runtime")
    assert k.location.line == 5 and "print(to_kelvin(25))" in k.message and k.evidence.code.highlight == [5]
    assert checks["import_effects:s"].status == "pass"
    assert "import_effects:script" not in checks


# ---- demo projects --------------------------------------------------------------------------------

MI = "MysteryInc/FirstLaunch"


def demo_spec() -> PracticalSpec:
    """Hand-built equivalent of the demo subject (independent of the subject parser)."""
    origin_rules = [BehaviorRule(when="speed <= limit", returns="True"), BehaviorRule(when=None, returns="False")]
    exercises = [
        ex("kelvin", f"{MI}/flight_functions/kelvin.py", fn("to_kelvin", "celsius: float", "float")),
        ex("safe_speed", f"{MI}/flight_functions/safe_speed.py", fn("is_safe", "speed: int, limit: int", "bool", rules=origin_rules)),
        ex("grade_landing", f"{MI}/flight_functions/grade_landing.py", fn("landing_grade", "vertical_speed: int", "str")),
        ex("fuel_share", f"{MI}/route_math/fuel_share.py", fn("fuel_share", "total_fuel: int, crew: int", "int"),
           fn("remaining_fuel", "total_fuel: int, crew: int", "int")),
        ex("mission_clock", f"{MI}/route_math/mission_clock.py", fn("mission_clock", "seconds: int", "str")),
        ex("FIXME2", f"{MI}/FIXME2.py", fn("average_speed", "distance: float, hours: float", "float")),
        ex("access_code", f"{MI}/access_code.py", kind="script", import_side_effects_allowed=True),
        ex("launch_sequence", f"{MI}/launch_sequence.py", kind="script", import_side_effects_allowed=True),
        ex("emoji_grade", f"{MI}/flight_functions/grade_landing.py", fn("emoji_grade", "vertical_speed: int", "str"), bonus=True),
        ex("max_altitude", f"{MI}/bonus/max_altitude.py", fn("max_altitude", "a: int, b: int, c: int", "int"), bonus=True),
        ex("countdown", f"{MI}/bonus/countdown.py", kind="script", bonus=True, import_side_effects_allowed=True),
    ]
    return PracticalSpec(
        exercises=exercises, global_constraints=DEMO_CONSTRAINTS,
        structure=StructureSpec(files=[FileRequirement(path=".gitignore")], require_gitignore=True))


def demo_run(variant: str, spec: PracticalSpec):
    root = DEMO_DIR / "projects" / f"mysteryinc_{variant}"
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    file_map: dict[str, str | None] = {}
    for req in spec.expected_files():   # exact path, else same basename elsewhere (misplaced)
        same_name = [f for f in files if f.rsplit("/", 1)[-1] == req.path.rsplit("/", 1)[-1]]
        file_map[req.path] = req.path if req.path in files else (same_name[0] if same_name else None)
    modules = analyze_project(root, files)
    checks = (check_syntax(modules, file_map, spec) + check_functions(spec, modules, file_map)
              + check_import_side_effects(spec, modules, file_map) + check_constraints(spec, modules, file_map))
    return by_id(checks)


def assert_buggy_detections(checks: dict) -> None:
    fs = checks["constraint:fuel_share:forbidden_builtin:round"]
    assert (fs.status, fs.severity, fs.location.file, fs.location.line) == ("fail", "critical", f"{MI}/route_math/fuel_share.py", 3)
    mx = checks["constraint:max_altitude:forbidden_builtin:max"]
    assert (mx.status, mx.mandatory, mx.bonus) == ("bonus", False, True)
    rf = checks["function:fuel_share:remaining_fuel"]
    assert rf.diagnosis == "wrong_function_name" and "remaining_fuels()" in rf.message
    sx = checks[f"syntax:{MI}/FIXME2.py"]
    assert (sx.status, sx.diagnosis, sx.location.line) == ("fail", "syntax_error", 3)
    sb = checks["returns:safe_speed:is_safe"]
    assert (sb.diagnosis, sb.location.line) == ("str_instead_of_bool", 4)
    kv = checks["import_effects:kelvin"]
    assert (kv.status, kv.diagnosis, kv.location.line) == ("warning", "import_side_effects", 6)
    mc = checks["returns:mission_clock:mission_clock"]
    assert (mc.diagnosis, mc.file, mc.location.file) == (
        "prints_instead_of_returns", f"{MI}/route_math/mission_clock.py", f"{MI}/mission_clock.py")
    em = checks["function:emoji_grade:emoji_grade"]
    assert (em.status, em.diagnosis) == ("bonus", "bonus_not_implemented")
    assert checks["function:FIXME2:average_speed"].status == "skipped"
    located = [c for c in checks.values() if c.status not in ("pass", "skipped") and c.location and c.location.line]
    assert located and all(c.evidence and c.evidence.code for c in located)


def assert_fixed_clean(checks: dict) -> None:
    bad = {k: (c.status, c.message) for k, c in checks.items() if c.status != "pass"}
    assert bad == {}
    assert "constraint:countdown:forbidden_builtin:*" in checks
    assert checks["returns:safe_speed:is_safe"].status == "pass"


def test_demo_buggy_project_detections():
    assert_buggy_detections(demo_run("buggy", demo_spec()))


def test_demo_fixed_project_has_no_failure():
    assert_fixed_clean(demo_run("fixed", demo_spec()))


def test_demo_with_heuristic_subject_parser():
    from premoulinette.subject.extract import extract_document
    from premoulinette.subject.heuristic import parse_heuristic

    subject = DEMO_DIR / "subject_demo.html"
    spec = parse_heuristic(extract_document(subject.read_bytes(), subject.name)).spec
    assert_buggy_detections(demo_run("buggy", spec))
    assert_fixed_clean(demo_run("fixed", spec))
