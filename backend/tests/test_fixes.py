"""Deterministic minimal fixes (explain/fixes.py).

``languages/python/static.py`` is written by another engineer in parallel, so ModuleInfo objects are built
here with a tiny local AST helper that fills only the fields the fix builders read.
"""
from __future__ import annotations

import ast
import copy

from conftest import FIXTURES_DIR

import premoulinette.explain.fixes as fixes_module
from premoulinette.explain.fixes import attach_fixes, build_fix
from premoulinette.languages.python.static_models import CallSite, FunctionInfo, ModuleInfo, ReturnInfo, StringLiteral
from premoulinette.results.models import (
    CheckResult,
    DiffLine,
    Evidence,
    Fix,
    Location,
    TextDiff,
    ValueSnapshot,
)

PROJECTS = FIXTURES_DIR / "projects"
SAFE_SPEED = "MysteryInc/FirstLaunch/flight_functions/safe_speed.py"
LAUNCH = "MysteryInc/FirstLaunch/launch_sequence.py"


# ---------------------------------------------------------------------------------------------
# Local stub of the static analyser (only what the fix builders need)
# ---------------------------------------------------------------------------------------------


def _return_info(node: ast.Return) -> ReturnInfo:
    if node.value is None:
        return ReturnInfo(line=node.lineno, value_src=None, value_kind="none")
    if isinstance(node.value, ast.Constant):
        return ReturnInfo(line=node.lineno, value_src=ast.unparse(node.value), value_kind="constant",
                          constant_type=type(node.value.value).__name__)
    kind = "call" if isinstance(node.value, ast.Call) else "name" if isinstance(node.value, ast.Name) else "expression"
    return ReturnInfo(line=node.lineno, value_src=ast.unparse(node.value), value_kind=kind)


def module_info(source: str, path: str) -> ModuleInfo:
    tree = ast.parse(source)
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    functions: list[FunctionInfo] = []
    strings: list[StringLiteral] = []
    calls: list[CallSite] = []

    def visit(node: ast.AST, fn: str | None, call: str | None) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append(StringLiteral(value=node.value, line=node.lineno, end_line=node.end_lineno or node.lineno,
                                         col=node.col_offset, end_col=node.end_col_offset or 0,
                                         in_call=call, in_function=fn))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            kind = "local" if name in defined else "builtin"
            calls.append(CallSite(name=name, kind=kind, line=node.lineno, col=node.col_offset, in_function=fn))
            for arg in node.args:
                visit(arg, fn, name if name in ("print", "input") else None)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, fn, None)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            returns = [_return_info(n) for n in ast.walk(node) if isinstance(n, ast.Return)]
            prints = sorted(n.lineno for n in ast.walk(node)
                            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print")
            functions.append(FunctionInfo(
                name=node.name, line=node.lineno, end_line=node.end_lineno or node.lineno, returns=returns,
                has_value_return=any(r.value_src not in (None, "None") for r in returns), prints=prints,
            ))
            for stmt in node.body:
                visit(stmt, node.name, None)
        else:
            visit(node, None, None)
    return ModuleInfo(path=path, ok=True, line_count=len(source.splitlines()), functions=functions,
                      strings=strings, calls=calls)


def project(path: str, source: str) -> tuple[dict[str, str], dict[str, ModuleInfo]]:
    return {path: source}, {path: module_info(source, path)}


def fixture_source(variant: str, rel: str) -> str:
    return (PROJECTS / variant / rel).read_text(encoding="utf-8")


def check(**kw: object) -> CheckResult:
    base: dict[str, object] = {"id": "x", "category": "functions", "status": "fail", "severity": "major",
                               "title": "t", "message": "m"}
    base.update(kw)
    return CheckResult(**base)  # type: ignore[arg-type]


def str_value(text: str) -> ValueSnapshot:
    return ValueSnapshot(repr=repr(text), type="str")


# ---------------------------------------------------------------------------------------------
# str_instead_of_bool / number_as_str
# ---------------------------------------------------------------------------------------------

IS_SAFE = '''def is_safe(speed: int, limit: int) -> bool:
    # We are safe as long as we do not go over the limit
    if speed <= limit:
        return "True"
    else:
        return "False"
'''

IS_SAFE_PATCH = '''--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
'''


def test_str_instead_of_bool_static_patch_is_exact():
    sources, modules = project(SAFE_SPEED, IS_SAFE)
    c = check(id="returns:safe_speed:is_safe", diagnosis="str_instead_of_bool", function="is_safe", file=SAFE_SPEED,
              location=Location(file=SAFE_SPEED, line=4))
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.patch == IS_SAFE_PATCH
    assert fix.file == SAFE_SPEED
    assert fix.confidence == "high"
    assert fix.before is None and fix.after is None   # two lines changed: no single-line convenience


def test_str_instead_of_bool_runtime_check_gives_the_same_patch():
    sources, modules = project(SAFE_SPEED, IS_SAFE)
    c = check(id="test:is_safe#ex1", category="explicit_tests", diagnosis="str_instead_of_bool", function="is_safe",
              file=SAFE_SPEED, location=Location(file=SAFE_SPEED, line=4),
              evidence=Evidence(call="is_safe(200, 250)", expected_value=ValueSnapshot(repr="True", type="bool"),
                                actual_value=str_value("True")))
    fix = build_fix(c, sources, modules)
    assert fix is not None and fix.patch == IS_SAFE_PATCH


def test_str_instead_of_bool_on_the_fixture_project_keeps_indentation():
    source = fixture_source("wrong_bool_type", SAFE_SPEED)
    sources, modules = project(SAFE_SPEED, source)
    c = check(id="returns:safe_speed:is_safe", diagnosis="str_instead_of_bool", function="is_safe", file=SAFE_SPEED)
    fix = build_fix(c, sources, modules)
    assert fix is not None and fix.patch is not None
    assert '-        return "True"\n+        return True\n' in fix.patch
    assert '-        return "False"\n+        return False\n' in fix.patch


def test_str_instead_of_bool_single_return_fills_before_after():
    src = 'def is_safe(speed, limit):\n    return "True" if speed <= limit else False\n'
    # IfExp: not a constant return -> nothing we can rewrite safely
    sources, modules = project("s.py", src)
    c = check(diagnosis="str_instead_of_bool", function="is_safe", file="s.py")
    assert build_fix(c, sources, modules) is None

    src = 'def is_ok(x):\n    if x:\n        return True\n    return "False"\n'
    sources, modules = project("s.py", src)
    fix = build_fix(check(diagnosis="str_instead_of_bool", function="is_ok", file="s.py"), sources, modules)
    assert fix is not None
    assert (fix.before, fix.after) == ('return "False"', "return False")


def test_str_instead_of_bool_returns_none_when_function_unknown():
    sources, modules = project(SAFE_SPEED, IS_SAFE)
    c = check(diagnosis="str_instead_of_bool", function="not_there", file=SAFE_SPEED)
    assert build_fix(c, sources, modules) is None
    c = check(diagnosis="str_instead_of_bool", function="is_safe", file="other.py")
    assert build_fix(c, sources, modules) is None


def test_number_as_str_only_for_constants():
    src = 'def fuel_share(total_fuel, crew):\n    if crew == 3:\n        return "133"\n    return str(total_fuel // crew)\n'
    sources, modules = project("f.py", src)
    c = check(category="explicit_tests", diagnosis="number_as_str", function="fuel_share", file="f.py",
              evidence=Evidence(expected_value=ValueSnapshot(repr="133", type="int"), actual_value=str_value("133")))
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.patch == ('--- a/f.py\n+++ b/f.py\n@@ -2,3 +2,3 @@\n     if crew == 3:\n-        return "133"\n'
                         '+        return 133\n     return str(total_fuel // crew)\n')

    # the received string comes from str(...), not from a constant: no patch
    c.evidence.actual_value = str_value("166")  # type: ignore[union-attr]
    assert build_fix(c, sources, modules) is None


# ---------------------------------------------------------------------------------------------
# Texts: prompts, printed lines, returned strings
# ---------------------------------------------------------------------------------------------


def prompt_check(expected: str, actual: str, line: int, file: str = LAUNCH) -> CheckResult:
    return check(id="prompt:launch_sequence:4", category="output", diagnosis="prompt_mismatch", severity="minor",
                 exercise_id="launch_sequence", file=file, location=Location(file=file, line=line),
                 evidence=Evidence(expected_value=str_value(expected), actual_value=str_value(actual),
                                   details={"expected_prompt": expected, "actual_prompt": actual}))


def test_prompt_typo_fix_on_the_fixture_project():
    source = fixture_source("wrong_prompt", LAUNCH)
    lines = source.splitlines()
    assert "callect" in lines[26]
    sources, modules = project(LAUNCH, source)
    c = prompt_check("Set a trap or collect evidence? (trap/evidence) ", "Set a trap or callect evidence? (trap/evidence) ", 27)
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.confidence == "high"
    assert fix.patch == (
        f"--- a/{LAUNCH}\n+++ b/{LAUNCH}\n@@ -26,3 +26,3 @@\n"
        f" {lines[25]}\n"
        '-    action = input("Set a trap or callect evidence? (trap/evidence) ")\n'
        '+    action = input("Set a trap or collect evidence? (trap/evidence) ")\n'
        f" {lines[27]}\n"
    )
    assert fix.before == 'action = input("Set a trap or callect evidence? (trap/evidence) ")'
    assert fix.after == 'action = input("Set a trap or collect evidence? (trap/evidence) ")'


def test_prompt_missing_trailing_space():
    src = 'pilot = input("Pilot name:")\nfuel = int(input("Starting fuel: "))\n'
    sources, modules = project("launch.py", src)
    fix = build_fix(prompt_check("Pilot name: ", "Pilot name:", 1, "launch.py"), sources, modules)
    assert fix is not None
    assert '-pilot = input("Pilot name:")\n+pilot = input("Pilot name: ")\n' in (fix.patch or "")


def test_prompt_fix_without_location_uses_the_unique_input_literal_with_medium_confidence():
    src = 'pilot = input("Pilot nam: ")\nprint("Pilot nam: is a label")\n'
    sources, modules = project("launch.py", src)
    c = prompt_check("Pilot name: ", "Pilot nam: ", 1, "launch.py")
    c.location = None
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.confidence == "medium"
    assert '+pilot = input("Pilot name: ")' in (fix.patch or "")


def test_ambiguous_literal_gives_no_fix():
    # the same text appears in two literals on the located line: no unambiguous edit
    src = 'x = input("Code: ") if True else input("Code: ")\n'
    sources, modules = project("a.py", src)
    assert build_fix(prompt_check("Code : ", "Code: ", 1, "a.py"), sources, modules) is None


def test_text_needing_escapes_gives_no_fix():
    src = 'name = input("Name: ")\n'
    sources, modules = project("a.py", src)
    assert build_fix(prompt_check('Name "x": ', "Name: ", 1, "a.py"), sources, modules) is None


def test_stdout_mismatch_single_source_line():
    src = 'code = input("Enter access code: ")\nif code == "SCOOBY":\n    print("Acces granted. Welcome aboard!")\nelse:\n    print("Access denied.")\n'
    sources, modules = project("access_code.py", src)
    diff = TextDiff(
        expected="Enter access code: Access granted. Welcome aboard!\n",
        actual="Enter access code: Acces granted. Welcome aboard!\n",
        equal=False, kinds=["typo"],
        lines=[DiffLine(op="changed", expected_lineno=1, actual_lineno=1,
                        expected="Enter access code: Access granted. Welcome aboard!",
                        actual="Enter access code: Acces granted. Welcome aboard!", expected_eol="\n", actual_eol="\n",
                        source=Location(file="access_code.py", line=3))],
    )
    c = check(id="test:access_code#session1", category="output", diagnosis="stdout_mismatch", file="access_code.py",
              evidence=Evidence(stdout_diff=diff))
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.patch == ('--- a/access_code.py\n+++ b/access_code.py\n@@ -2,3 +2,3 @@\n if code == "SCOOBY":\n'
                         '-    print("Acces granted. Welcome aboard!")\n+    print("Access granted. Welcome aboard!")\n'
                         ' else:\n')

    # missing/extra lines are not a one-line edit
    diff.lines.append(DiffLine(op="missing", expected_lineno=2, expected="Bye", expected_eol="\n"))
    assert build_fix(c, sources, modules) is None


def test_wrong_string_returned_literal():
    src = 'def landing_grade(v):\n    if v <= 2:\n        return "Perfect touchdown"\n    if v <= 5:\n        return "Hard Landing"\n    return "Crash!"\n'
    sources, modules = project("g.py", src)
    c = check(category="explicit_tests", diagnosis="wrong_string", function="landing_grade", file="g.py",
              location=Location(file="g.py", line=5),
              evidence=Evidence(expected_value=str_value("Hard landing"), actual_value=str_value("Hard Landing")))
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert '-        return "Hard Landing"\n+        return "Hard landing"\n' in (fix.patch or "")


# ---------------------------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------------------------


def test_wrong_function_name_renames_the_def_line():
    source = fixture_source("wrong_function_name", SAFE_SPEED)
    sources, modules = project(SAFE_SPEED, source)
    c = check(id="function:safe_speed:is_safe", diagnosis="wrong_function_name", severity="critical", function="is_safe",
              file=SAFE_SPEED, location=Location(file=SAFE_SPEED, line=1),
              message="Function 'is_safe' not found; a similar function 'is_save' is defined (line 1).")
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.patch == (
        f"--- a/{SAFE_SPEED}\n+++ b/{SAFE_SPEED}\n@@ -1,2 +1,2 @@\n"
        "-def is_save(speed: int, limit: int) -> bool:\n"
        "+def is_safe(speed: int, limit: int) -> bool:\n"
        "     # We are safe as long as we do not go over the limit\n"
    )
    assert (fix.before, fix.after) == ("def is_save(speed: int, limit: int) -> bool:", "def is_safe(speed: int, limit: int) -> bool:")
    assert "is_save" in fix.summary and "is_safe" in fix.summary


def test_wrong_function_name_mentions_call_sites():
    src = "def to_kelvn(celsius):\n    return celsius + 273.15\n\n\nif __name__ == '__main__':\n    print(to_kelvn(0))\n"
    sources, modules = project("k.py", src)
    c = check(diagnosis="wrong_function_name", function="to_kelvin", file="k.py",
              evidence=Evidence(details={"found": "to_kelvn"}))
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert "+def to_kelvin(celsius):" in (fix.patch or "")
    assert "line(s) 6" in fix.summary


def test_prints_instead_of_returns():
    src = "def to_kelvin(celsius: float) -> float:\n    print(celsius + 273.15)  # result\n"
    sources, modules = project("k.py", src)
    c = check(id="returns:kelvin:to_kelvin", diagnosis="prints_instead_of_returns", function="to_kelvin", file="k.py")
    fix = build_fix(c, sources, modules)
    assert fix is not None
    assert fix.confidence == "medium"
    assert fix.patch == ("--- a/k.py\n+++ b/k.py\n@@ -1,2 +1,2 @@\n def to_kelvin(celsius: float) -> float:\n"
                         "-    print(celsius + 273.15)  # result\n+    return celsius + 273.15  # result\n")


def test_prints_instead_of_returns_refuses_unsafe_cases():
    loop = "def countdown(n):\n    for i in range(n):\n        print(i)\n"
    two = "def f(x):\n    print('debug')\n    print(x)\n"
    returns = "def f(x):\n    print(x)\n    return x\n"
    for src, fn in ((loop, "countdown"), (two, "f"), (returns, "f")):
        sources, modules = project("p.py", src)
        assert build_fix(check(diagnosis="prints_instead_of_returns", function=fn, file="p.py"), sources, modules) is None


# ---------------------------------------------------------------------------------------------
# Repository: files and git
# ---------------------------------------------------------------------------------------------


def test_missing_gitignore_creates_the_file():
    c = check(id="structure:gitignore", category="structure", diagnosis="missing_gitignore", file=".gitignore")
    fix = build_fix(c, {}, {})
    assert fix is not None
    assert fix.patch == "--- /dev/null\n+++ b/.gitignore\n@@ -0,0 +1,3 @@\n+__pycache__/\n+*.pyc\n+.DS_Store\n"


def test_parasite_file_is_a_summary_with_git_rm_cached():
    path = "MysteryInc/FirstLaunch/__pycache__/kelvin.cpython-312.pyc"
    c = check(id=f"structure:parasite:{path}", category="structure", diagnosis="parasite_file", file=path)
    fix = build_fix(c, {}, {})
    assert fix is not None
    assert fix.patch is None
    assert f"git rm -r --cached {path}" in fix.summary
    assert "__pycache__/" in fix.summary and ".gitignore" in fix.summary


def test_misplaced_file_and_wrong_case_use_git_mv():
    c = check(id="structure:file:MysteryInc/FirstLaunch/route_math/fuel_share.py", category="structure",
              diagnosis="misplaced_file", severity="critical",
              evidence=Evidence(details={"expected_path": "MysteryInc/FirstLaunch/route_math/fuel_share.py",
                                         "found_path": "MysteryInc/FirstLaunch/fuel_share.py"}))
    fix = build_fix(c, {}, {})
    assert fix is not None
    assert fix.after == "git mv MysteryInc/FirstLaunch/fuel_share.py MysteryInc/FirstLaunch/route_math/fuel_share.py"

    c = check(id="structure:file:MysteryInc/FirstLaunch/flight_functions/kelvin.py", category="structure",
              diagnosis="wrong_case_path", severity="critical",
              evidence=Evidence(details={"found_path": "MysteryInc/FirstLaunch/flight_functions/Kelvin.py"}))
    fix = build_fix(c, {}, {})
    assert fix is not None
    assert fix.after == (
        "git mv MysteryInc/FirstLaunch/flight_functions/Kelvin.py MysteryInc/FirstLaunch/flight_functions/Kelvin.py.tmp\n"
        "git mv MysteryInc/FirstLaunch/flight_functions/Kelvin.py.tmp MysteryInc/FirstLaunch/flight_functions/kelvin.py"
    )


def test_untracked_file_is_git_add_only():
    path = "MysteryInc/FirstLaunch/access_code.py"
    c = check(id=f"git:untracked:{path}", category="git", diagnosis="untracked_file", file=path)
    fix = build_fix(c, {}, {})
    assert fix is not None
    assert fix.after == f"git add {path}"
    text = f"{fix.summary} {fix.after}".lower()
    assert "push" not in text and "tag" not in text


def test_paths_with_spaces_are_quoted():
    c = check(id="git:untracked:my dir/a.py", category="git", diagnosis="untracked_file")
    fix = build_fix(c, {}, {})
    assert fix is not None and fix.after == "git add 'my dir/a.py'"


def test_forbidden_builtin_is_a_low_confidence_hint_without_patch():
    c = check(id="constraint:max_altitude:forbidden_builtin:max", category="constraints", diagnosis="forbidden_builtin",
              file="m.py")
    fix = build_fix(c, {}, {})
    assert fix is not None
    assert fix.patch is None and fix.confidence == "low"
    assert "max()" in fix.summary and "compare" in fix.summary


# ---------------------------------------------------------------------------------------------
# attach_fixes
# ---------------------------------------------------------------------------------------------


def test_attach_fixes_only_touches_failing_checks_and_never_mutates_sources():
    sources, modules = project(SAFE_SPEED, IS_SAFE)
    snapshot = copy.deepcopy(sources)
    failing = check(diagnosis="str_instead_of_bool", function="is_safe", file=SAFE_SPEED)
    passing = check(status="pass", severity=None, diagnosis="str_instead_of_bool", function="is_safe", file=SAFE_SPEED)
    already = check(diagnosis="str_instead_of_bool", function="is_safe", file=SAFE_SPEED, fix=Fix(summary="keep me"))
    unknown = check(diagnosis="wrong_value", function="is_safe", file=SAFE_SPEED)
    attach_fixes([failing, passing, already, unknown], sources, modules)
    assert failing.fix is not None and failing.fix.patch == IS_SAFE_PATCH
    assert passing.fix is None
    assert already.fix is not None and already.fix.summary == "keep me"
    assert unknown.fix is None
    assert sources == snapshot


def test_inconsistent_module_info_gives_no_fix():
    sources = {"s.py": 'def is_safe(a, b):\n    return "True"\n'}
    broken = ModuleInfo(path="s.py", ok=True, functions=[FunctionInfo(
        name="is_safe", line=1, end_line=2, returns=[ReturnInfo(line=99, value_src="'True'", value_kind="constant")])])
    c = check(diagnosis="str_instead_of_bool", function="is_safe", file="s.py")
    assert build_fix(c, sources, {"s.py": broken}) is None


def test_builder_exceptions_never_propagate(monkeypatch):
    def boom(*_: object) -> Fix:
        raise RuntimeError("bug in a builder")

    monkeypatch.setitem(fixes_module._BUILDERS, "str_instead_of_bool", boom)
    c = check(diagnosis="str_instead_of_bool", function="is_safe", file=SAFE_SPEED)
    assert build_fix(c, *project(SAFE_SPEED, IS_SAFE)) is None
    attach_fixes([c], *project(SAFE_SPEED, IS_SAFE))
    assert c.fix is None
