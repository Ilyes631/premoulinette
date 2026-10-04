"""Realistic AnalysisReport builders for tests, modelled on demo/subject_demo.html.

Reusable by any test module (``backend/tests`` is on sys.path under pytest)::

    from report_factory import make_report, make_spec, passing_checks, buggy_checks, hostile_check

* ``make_spec()``        — PracticalSpec of "TP 1 — MysteryInc: First Launch" (8 mandatory + 3 bonus exercises).
* ``passing_checks()``   — every check passing (verdict "ready", confidence "high").
* ``buggy_checks()``     — the classic student mistakes: wrong-case file, parasite, str instead of bool,
                           typo, missing trailing space, forbidden builtin, crash, untracked file, missing bonus...
* ``hostile_check()``    — a check whose strings contain HTML/script payloads (escaping tests).
* ``make_report()``      — AnalysisReport with the score computed by ``scoring.score.compute_score``.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone

from premoulinette.results.models import (
    AnalysisReport,
    CheckResult,
    CodeExcerpt,
    DiffLine,
    DiffSegment,
    Evidence,
    ExceptionInfo,
    Fix,
    GitInfo,
    Location,
    ProjectSummary,
    SandboxInfo,
    SubjectSummary,
    TextDiff,
    TreeEntry,
    ValueSnapshot,
)
from premoulinette.scoring.score import compute_score
from premoulinette.spec.models import (
    BehaviorRule,
    Constraints,
    ExerciseSpec,
    FileRequirement,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    InteractionStep,
    Origin,
    Param,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
    SpecMetadata,
    StructureSpec,
    explicit,
)

SUBJECT_TITLE = "TP 1 — MysteryInc: First Launch"
ROOT = "MysteryInc/FirstLaunch"
P_KELVIN = f"{ROOT}/flight_functions/kelvin.py"
P_SAFE = f"{ROOT}/flight_functions/safe_speed.py"
P_GRADE = f"{ROOT}/flight_functions/grade_landing.py"
P_FUEL = f"{ROOT}/route_math/fuel_share.py"
P_CLOCK = f"{ROOT}/route_math/mission_clock.py"
P_FIXME = f"{ROOT}/FIXME2.py"
P_ACCESS = f"{ROOT}/access_code.py"
P_LAUNCH = f"{ROOT}/launch_sequence.py"
P_COUNTDOWN = f"{ROOT}/bonus/countdown.py"
P_MAXALT = f"{ROOT}/bonus/max_altitude.py"

ALLOWED_BUILTINS = ["input", "print", "len", "int", "str", "float", "bool"]
FORBIDDEN_BUILTINS = ["abs", "max", "min", "round", "sorted", "sum", "eval"]


# ---- spec ----------------------------------------------------------------------------------------

def _fn(name: str, params: list[tuple[str, str]], ret: str, examples: list[tuple[list[str], str]], section: str,
        *, rules: list[tuple[str | None, str]] | None = None, reference: str | None = None) -> FunctionSpec:
    sig = FunctionSignature(name=name, params=[Param(name=n, annotation=a) for n, a in params], return_annotation=ret)
    tests = [
        FunctionTest(id=f"{name}#ex{i}", function=name, args=args, expected_return=expected,
                     origin=explicit(f">>> {name}({', '.join(args)})", section))
        for i, (args, expected) in enumerate(examples, start=1)
    ]
    return FunctionSpec(
        signature=sig, reference=reference, tests=tests, origin=explicit(sig.render() + ":", section),
        rules=[BehaviorRule(when=w, returns=r, origin=explicit(f"{w or 'otherwise'} → {r}", section))
               for w, r in rules or []],
    )


def _fn_ex(ex_id: str, title: str, path: str, fns: list[FunctionSpec], *, bonus: bool = False) -> ExerciseSpec:
    return ExerciseSpec(id=ex_id, title=title, kind="functions", bonus=bonus, file_path=path, functions=fns,
                        origin=explicit(f"File: {path}", title))


def _script_ex(ex_id: str, title: str, path: str, prompts: list[str], sessions: list[list[tuple[str, str]]],
               *, bonus: bool = False) -> ExerciseSpec:
    tests = [
        ScriptTest(id=f"{ex_id}#session{i}", steps=[InteractionStep(kind=k, text=t) for k, t in steps],
                   origin=explicit(f"42sh$ python3 {path.rsplit('/', 1)[-1]}", title))
        for i, steps in enumerate(sessions, start=1)
    ]
    return ExerciseSpec(id=ex_id, title=title, kind="script", bonus=bonus, file_path=path,
                        script=ScriptSpec(prompts=prompts, tests=tests, origin=explicit(None, title)),
                        import_side_effects_allowed=True, origin=explicit(f"File: {path}", title))


_MENU = "Where's the Mystery Machine headed today?\n1 - Crystal Cove\n2 - The Old Mill\n3 - Spooky Swamp\n"
_TRAP = "Set a trap or collect evidence? (trap/evidence) "


def _launch_session(name: str, fuel: str, choice: str, tail: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [("output", "Pilot name: "), ("input", name), ("output", "Starting fuel: "), ("input", fuel),
            ("output", _MENU + "Your choice: "), ("input", choice), *tail]


def make_spec(*, notes: list[str] | None = None, ai_extracted_rule: bool = False) -> PracticalSpec:
    e1, e2, e3 = "Exercise 1 — Kelvin", "Exercise 2 — Safe speed", "Exercise 3 — Landing grade"
    e4, e5, e6 = "Exercise 4 — Fuel share", "Exercise 5 — Mission clock", "Exercise 6 — FIXME"
    landing_rules = [("vertical_speed <= 2", "'Perfect touchdown'"), ("2 < vertical_speed <= 5", "'Hard landing'"),
                     ("vertical_speed > 5", "'Crash!'")]
    exercises = [
        _fn_ex("kelvin", e1, P_KELVIN, [_fn("to_kelvin", [("celsius", "float")], "float",
               [(["0"], "273.15"), (["100"], "373.15"), (["-273.15"], "0.0")], e1, reference="celsius + 273.15")]),
        _fn_ex("safe_speed", e2, P_SAFE, [_fn("is_safe", [("speed", "int"), ("limit", "int")], "bool",
               [(["200", "250"], "True"), (["300", "250"], "False")], e2,
               rules=[("speed <= limit", "True"), (None, "False")])]),
        _fn_ex("grade_landing", e3, P_GRADE, [_fn("landing_grade", [("vertical_speed", "int")], "str",
               [(["1"], "'Perfect touchdown'"), (["4"], "'Hard landing'"), (["9"], "'Crash!'")], e3,
               rules=landing_rules)]),
        _fn_ex("fuel_share", e4, P_FUEL, [
            _fn("fuel_share", [("total_fuel", "int"), ("crew", "int")], "int", [(["400", "3"], "133"), (["500", "3"], "166")],
                e4, reference="total_fuel // crew"),
            _fn("remaining_fuel", [("total_fuel", "int"), ("crew", "int")], "int", [(["400", "3"], "1")], e4,
                reference="total_fuel % crew"),
        ]),
        _fn_ex("mission_clock", e5, P_CLOCK, [_fn("mission_clock", [("seconds", "int")], "str",
               [(["3725"], "'01:02:05'"), (["0"], "'00:00:00'")], e5,
               reference='f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"')]),
        _fn_ex("FIXME2", e6, P_FIXME, [_fn("average_speed", [("distance", "float"), ("hours", "float")], "float",
               [(["150.0", "2.0"], "75.0"), (["10.0", "0.0"], "0.0")], e6,
               rules=[("hours == 0", "0.0"), (None, "distance / hours")])]),
        _script_ex("access_code", "Exercise 7 — Access code", P_ACCESS, ["Enter access code: "], [
            [("output", "Enter access code: "), ("input", "SCOOBY"), ("output", "Access granted. Welcome aboard!\n")],
            [("output", "Enter access code: "), ("input", "scooby"), ("output", "Access denied.\n")],
        ]),
        _script_ex("launch_sequence", "Exercise 8 — Launch sequence", P_LAUNCH,
                   ["Pilot name: ", "Starting fuel: ", "Your choice: ", _TRAP], [
            _launch_session("Camille", "400", "2", [
                ("output", "Destination: The Old Mill\nFuel after the trip: 280\n" + _TRAP), ("input", "trap"),
                ("output", "Camille sets a trap at The Old Mill. Zoinks!\n")]),
            _launch_session("Fred", "100", "3", [("output", "Not enough fuel! The gang stays home.\n")]),
            _launch_session("Velma", "250", "1", [
                ("output", "Destination: Crystal Cove\nFuel after the trip: 200\n" + _TRAP), ("input", "evidence"),
                ("output", "Velma collects evidence at Crystal Cove. Jinkies!\n")]),
        ]),
        _fn_ex("emoji_grade", "Bonus 1 — Emoji grade", P_GRADE, [_fn("emoji_grade", [("vertical_speed", "int")], "str",
               [(["0"], "'🟢'"), (["7"], "'🔴'")], "Bonus 1 — Emoji grade",
               rules=[("vertical_speed <= 2", "'🟢'"), ("2 < vertical_speed <= 5", "'🟡'"), ("vertical_speed > 5", "'🔴'")])],
               bonus=True),
        _fn_ex("max_altitude", "Bonus 2 — Max altitude", P_MAXALT, [_fn("max_altitude",
               [("a", "int"), ("b", "int"), ("c", "int")], "int",
               [(["120", "450", "300"], "450"), (["-5", "-2", "-9"], "-2")], "Bonus 2 — Max altitude")], bonus=True),
        _script_ex("countdown", "Bonus 3 — Countdown", P_COUNTDOWN, ["Countdown start: "], [
            [("output", "Countdown start: "), ("input", "3"), ("output", "3\n2\n1\nLiftoff!\n")]], bonus=True),
    ]
    if ai_extracted_rule:
        fn = exercises[1].functions[0]
        fn.rules.append(BehaviorRule(when="speed < 0", returns="False",
                                     origin=Origin(provenance="ai_extracted", confidence=0.5)))
    files = [FileRequirement(path=".gitignore", origin=explicit("must contain a .gitignore file", "Submission"))]
    for path in (P_GRADE, P_KELVIN, P_SAFE, P_FUEL, P_CLOCK, P_COUNTDOWN, P_MAXALT, P_FIXME, P_ACCESS, P_LAUNCH):
        bonus = "/bonus/" in path
        files.append(FileRequirement(path=path, required=not bonus, bonus=bonus, origin=explicit(path, "Submission")))
    return PracticalSpec(
        metadata=SpecMetadata(title=SUBJECT_TITLE, course="Programming S1 — Python", deadline="Sunday 23:42",
                              source_name="subject_demo.html"),
        structure=StructureSpec(files=files, forbidden_patterns_are_errors=True, require_gitignore=True),
        global_constraints=Constraints(allowed_builtins=ALLOWED_BUILTINS, forbidden_builtins=FORBIDDEN_BUILTINS,
                                       allowed_imports=[], origin=explicit("Authorized builtins", "Rules")),
        exercises=exercises,
        notes=list(notes or []),
    )


# ---- text diffs ----------------------------------------------------------------------------------

def _split_eol(raw: str) -> tuple[str, str]:
    return (raw[:-1], "\n") if raw.endswith("\n") else (raw, "")


def text_diff(expected: str, actual: str, *, hints: dict[int, list[str]] | None = None,
              sources: dict[int, Location] | None = None) -> TextDiff:
    """Small line-by-line diff (same line count) with char segments, like compare.text_diff would produce."""
    hints, sources = hints or {}, sources or {}
    exp_lines, act_lines = expected.splitlines(keepends=True), actual.splitlines(keepends=True)
    assert len(exp_lines) == len(act_lines), "report_factory.text_diff only aligns equal line counts"
    lines: list[DiffLine] = []
    for n, (e_raw, a_raw) in enumerate(zip(exp_lines, act_lines), start=1):
        (e, e_eol), (a, a_eol) = _split_eol(e_raw), _split_eol(a_raw)
        common = dict(expected_lineno=n, actual_lineno=n, expected=e, actual=a, expected_eol=e_eol, actual_eol=a_eol,
                      source=sources.get(n))
        if e_raw == a_raw:
            lines.append(DiffLine(op="equal", **common))
            continue
        segments = [DiffSegment(op=tag, expected=e[i1:i2], actual=a[j1:j2])
                    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, e, a, autojunk=False).get_opcodes()]
        lines.append(DiffLine(op="changed", segments=segments, hints=hints.get(n, []), **common))
    first = next((i for i, (x, y) in enumerate(zip(expected, actual)) if x != y), min(len(expected), len(actual)))
    changed = sum(1 for d in lines if d.op != "equal")
    return TextDiff(expected=expected, actual=actual, equal=expected == actual, lines=lines,
                    kinds=[] if expected == actual else ["typo"],
                    summary="" if expected == actual else f"{changed} line(s) differ",
                    first_difference=None if expected == actual else first)


# ---- checks --------------------------------------------------------------------------------------

def _check(cid: str, category: str, status: str, title: str, message: str, **kw: object) -> CheckResult:
    return CheckResult(id=cid, category=category, status=status, title=title, message=message, **kw)


def _flags(ex: ExerciseSpec | None) -> dict[str, object]:
    return {"mandatory": False, "bonus": True} if ex is not None and ex.bonus else {}


def passing_checks(spec: PracticalSpec | None = None) -> list[CheckResult]:
    spec = spec or make_spec()
    by_file = {e.file_path: e for e in spec.exercises if not e.bonus}
    by_file.update({e.file_path: e for e in spec.exercises if e.bonus and e.file_path not in by_file})
    out: list[CheckResult] = []
    for req in spec.expected_files():
        flags = {"mandatory": False, "bonus": True} if req.bonus else {}
        out.append(_check(f"structure:file:{req.path}", "structure", "pass", "File present",
                          f"'{req.path}' exists with the exact expected name.", file=req.path, **flags))
    out.append(_check("structure:gitignore", "structure", "pass", ".gitignore present",
                      "The repository contains a .gitignore file.", file=".gitignore"))
    for req in spec.expected_files():
        if req.path.endswith(".py"):
            flags = {"mandatory": False, "bonus": True} if req.bonus else {}
            out.append(_check(f"syntax:{req.path}", "syntax", "pass", "Compiles", f"'{req.path}' parses without error.",
                              file=req.path, **flags))
    for ex in spec.exercises:
        out.extend(_exercise_passing_checks(ex, spec))
    return out


def _exercise_passing_checks(ex: ExerciseSpec, spec: PracticalSpec) -> list[CheckResult]:
    flags = _flags(ex)
    common = {"exercise_id": ex.id, "file": ex.file_path, **flags}
    out: list[CheckResult] = []
    for fn in ex.functions:
        out.append(_check(f"function:{ex.id}:{fn.name}", "functions", "pass", "Function defined",
                          f"'{fn.name}' is defined in {ex.file_path}.", function=fn.name, **common))
        out.append(_check(f"signature:{ex.id}:{fn.name}", "functions", "pass", "Signature matches",
                          f"{fn.signature.render()} matches the subject.", function=fn.name, **common))
        for t in fn.tests:
            out.append(_check(f"test:{t.id}", "explicit_tests", "pass", "Example from the subject",
                              f"{t.call_repr()} returned {t.expected_return}.", function=fn.name, test_id=t.id,
                              origin=t.origin, evidence=Evidence(call=t.call_repr()), **common))
        if fn.rules or fn.reference:
            for i in (1, 2):
                tid = f"{fn.name}#derived{i}"
                out.append(_check(f"test:{tid}", "derived_tests", "pass", "Boundary case",
                                  f"Derived case {i} for {fn.name} passed.", function=fn.name, test_id=tid,
                                  origin=Origin(provenance="derived", confidence=0.9), **common))
        out.append(_check(f"test:{fn.name}#heur1", "heuristic_tests", "pass", "Extra case (heuristic)",
                          f"Heuristic case for {fn.name} did not crash.", function=fn.name, test_id=f"{fn.name}#heur1",
                          origin=Origin(provenance="heuristic", confidence=0.5),
                          **{**common, "mandatory": False}))
    if ex.script is not None:
        for t in ex.script.tests:
            out.append(_check(f"test:{t.id}", "output", "pass", "Output matches the subject",
                              "The program output is identical to the subject transcript.", test_id=t.id,
                              origin=t.origin, evidence=Evidence(stdin=t.stdin, expected_stdout=t.expected_stdout,
                                                                 actual_stdout=t.expected_stdout), **common))
        for n, prompt in enumerate(ex.script.prompts, start=1):
            out.append(_check(f"prompt:{ex.id}:{n}", "output", "pass", "Prompt matches",
                              f"Prompt {n} is exactly {prompt!r}.", **common))
    else:
        out.append(_check(f"import_effects:{ex.id}", "runtime", "pass", "Import is silent",
                          "Importing the module prints nothing and does not wait for input.", **common))
    for name in spec.effective_constraints(ex).forbidden_builtins:
        out.append(_check(f"constraint:{ex.id}:forbidden_builtin:{name}", "constraints", "pass",
                          f"{name}() not used", f"Forbidden builtin {name}() is not used.", **common))
    return out


def _excerpt(path: str, start: int, lines: list[str], highlight: int) -> CodeExcerpt:
    return CodeExcerpt(file=path, start_line=start, lines=lines, highlight=[highlight])


def _launch_actual(expected: str) -> str:
    return expected.replace("Fuel after the trip: ", "Fuel after trip: ").replace(_TRAP, _TRAP.rstrip(" "))


def buggy_checks(spec: PracticalSpec | None = None) -> list[CheckResult]:
    """Passing baseline with the typical mistakes of demo/projects/mysteryinc_buggy applied."""
    spec = spec or make_spec()
    checks = {c.id: c for c in passing_checks(spec)}

    def put(cid: str, **changes: object) -> None:
        checks[cid] = checks[cid].model_copy(update=changes)

    put(f"structure:file:{P_FIXME}", status="fail", severity="critical", diagnosis="wrong_case_path",
        title="Wrong file name case",
        message=f"Expected '{P_FIXME}' but found '{ROOT}/Fixme2.py': the grader is case-sensitive.",
        location=Location(file=f"{ROOT}/Fixme2.py"),
        fix=Fix(summary="Rename the file with git mv.", before=f"{ROOT}/Fixme2.py", after=P_FIXME))

    safe_code = _excerpt(P_SAFE, 1, ["def is_safe(speed: int, limit: int) -> bool:", "    if speed <= limit:",
                                     '        return "True"', '    return "False"'], 3)
    for n, (args, exp) in enumerate([("200, 250", "True"), ("300, 250", "False")], start=1):
        put(f"test:is_safe#ex{n}", status="fail", severity="major", diagnosis="str_instead_of_bool",
            title="Wrong return type", message=f"is_safe({args}) returned the string '{exp}' instead of the boolean {exp}.",
            location=Location(file=P_SAFE, line=3 if n == 1 else 4),
            evidence=Evidence(call=f"is_safe({args})", expected_value=ValueSnapshot(repr=exp, type="bool"),
                              actual_value=ValueSnapshot(repr=f"'{exp}'", type="str"), rule="speed <= limit",
                              code=safe_code),
            fix=Fix(summary="Return a real boolean.", file=P_SAFE,
                    patch=f'--- a/{P_SAFE}\n+++ b/{P_SAFE}\n@@ -2,3 +2,3 @@\n     if speed <= limit:\n'
                          '-        return "True"\n+        return True\n     return "False"\n'))
    checks["returns:safe_speed:is_safe"] = _check(
        "returns:safe_speed:is_safe", "functions", "fail", "Returns a string instead of a boolean",
        'is_safe returns the constants "True"/"False" (str) but is annotated -> bool.', severity="major",
        diagnosis="str_instead_of_bool", exercise_id="safe_speed", function="is_safe", file=P_SAFE,
        location=Location(file=P_SAFE, line=3))

    put("test:landing_grade#ex2", status="fail", severity="minor", diagnosis="wrong_string", title="Wrong string",
        message="landing_grade(4) returned 'Hard landng' instead of 'Hard landing' (1 character differs).",
        location=Location(file=P_GRADE, line=5),
        evidence=Evidence(call="landing_grade(4)", expected_value=ValueSnapshot(repr="'Hard landing'", type="str"),
                          actual_value=ValueSnapshot(repr="'Hard landng'", type="str"),
                          value_diff=text_diff("Hard landing", "Hard landng", hints={1: ["typo: missing 'i'"]}),
                          rule="2 < vertical_speed <= 5"))

    session = spec.exercise("launch_sequence").script.tests[0]
    actual = _launch_actual(session.expected_stdout)
    trap_line = session.expected_stdout.splitlines().index(_TRAP + "Camille sets a trap at The Old Mill. Zoinks!") + 1
    put("test:launch_sequence#session1", status="fail", severity="major", diagnosis="stdout_mismatch",
        title="Output differs from the subject", message="2 lines of output differ from the expected transcript.",
        location=Location(file=P_LAUNCH, line=21),
        evidence=Evidence(stdin=session.stdin, expected_stdout=session.expected_stdout, actual_stdout=actual,
                          exit_code=0, stdout_diff=text_diff(
                              session.expected_stdout, actual,
                              hints={trap_line - 1: ["missing word 'the'"], trap_line: ["missing trailing space"]},
                              sources={trap_line - 1: Location(file=P_LAUNCH, line=21),
                                       trap_line: Location(file=P_LAUNCH, line=22)})))
    put("prompt:launch_sequence:4", status="fail", severity="minor", diagnosis="prompt_mismatch",
        title="Prompt differs", message="Prompt 4 is missing its trailing space.", location=Location(file=P_LAUNCH, line=22),
        evidence=Evidence(value_diff=text_diff(_TRAP, _TRAP.rstrip(" ")),
                          expected_value=ValueSnapshot(repr=repr(_TRAP), type="str"),
                          actual_value=ValueSnapshot(repr=repr(_TRAP.rstrip(" ")), type="str")),
        fix=Fix(summary="Add the trailing space to the prompt.", file=P_LAUNCH,
                before='input("Set a trap or collect evidence? (trap/evidence)")',
                after='input("Set a trap or collect evidence? (trap/evidence) ")'))

    put("constraint:FIXME2:forbidden_builtin:round", status="fail", severity="critical", diagnosis="forbidden_builtin",
        title="Forbidden builtin round()", message="round() is forbidden by the subject (used on line 4).",
        location=Location(file=P_FIXME, line=4),
        evidence=Evidence(code=_excerpt(P_FIXME, 1, ["def average_speed(distance: float, hours: float) -> float:",
                                                     "    speed = distance / hours",
                                                     "    # TODO", "    return round(speed, 2)"], 4)),
        fix=Fix(summary="Remove round(): return the exact division.", confidence="low"))
    crash = ExceptionInfo(type="ZeroDivisionError", message="float division by zero",
                          traceback=f'  File "{P_FIXME}", line 2, in average_speed\n'
                                    "    speed = distance / hours\nZeroDivisionError: float division by zero",
                          location=Location(file=P_FIXME, line=2))
    put("test:average_speed#ex2", status="fail", severity="critical", diagnosis="exception", title="Crash",
        message="average_speed(10.0, 0.0) raised ZeroDivisionError.", location=Location(file=P_FIXME, line=2),
        evidence=Evidence(call="average_speed(10.0, 0.0)", expected_value=ValueSnapshot(repr="0.0", type="float"),
                          exception=crash, rule="hours == 0 → 0.0"))
    put("test:average_speed#derived1", status="fail", severity="critical", diagnosis="exception", title="Crash",
        message="average_speed(1.0, 0) raised ZeroDivisionError.", location=Location(file=P_FIXME, line=2),
        evidence=Evidence(call="average_speed(1.0, 0)", exception=crash, rule="hours == 0"))

    put("import_effects:mission_clock", status="warning", severity="major", diagnosis="import_side_effects",
        title="Code runs at import", message="Line 7 calls print() at the top level: it runs when the grader imports the file.",
        location=Location(file=P_CLOCK, line=7))
    put("test:mission_clock#heur1", status="warning", severity="minor", diagnosis="wrong_value",
        title="Extra case (heuristic)", message="mission_clock(86400) returned '24:00:00'; a 'days' field may be expected.",
        evidence=Evidence(call="mission_clock(86400)", actual_value=ValueSnapshot(repr="'24:00:00'", type="str")))

    # Bonus: countdown.py missing, max_altitude uses max().
    put(f"structure:file:{P_COUNTDOWN}", status="bonus", diagnosis="missing_bonus_file", title="Bonus file missing",
        message=f"Optional bonus file '{P_COUNTDOWN}' is not present.")
    put(f"syntax:{P_COUNTDOWN}", status="bonus", blocked_by=f"structure:file:{P_COUNTDOWN}", title="Not compiled",
        message="The bonus file is missing.")
    put("test:countdown#session1", status="bonus", blocked_by=f"structure:file:{P_COUNTDOWN}", title="Not run",
        message="The bonus file is missing.")
    put("prompt:countdown:1", status="bonus", blocked_by=f"structure:file:{P_COUNTDOWN}", title="Not run",
        message="The bonus file is missing.")
    put("constraint:max_altitude:forbidden_builtin:max", status="bonus", severity="critical",
        diagnosis="forbidden_builtin", title="Forbidden builtin max()", message="max() is forbidden by the subject.",
        location=Location(file=P_MAXALT, line=2))

    extra = [
        _check(f"structure:parasite:{ROOT}/flight_functions/__pycache__/", "structure", "fail", "Forbidden file",
               "__pycache__/ must not be pushed.", severity="major", diagnosis="parasite_file",
               file=f"{ROOT}/flight_functions/__pycache__/"),
        _check(f"structure:extra:{ROOT}/notes.py", "structure", "info", "Extra file", "notes.py is not part of the subject.",
               diagnosis="extra_file", file=f"{ROOT}/notes.py", mandatory=False),
        _check(f"git:untracked:{P_LAUNCH}", "git", "fail", "File not tracked by git",
               f"'{P_LAUNCH}' is not tracked: it will not be submitted.", severity="major", diagnosis="untracked_file",
               file=P_LAUNCH),
        _check("git:dirty", "git", "warning", "Uncommitted changes", "2 modified files are not committed.",
               severity="minor", diagnosis="dirty_tree"),
    ]
    return list(checks.values()) + extra


def hostile_check() -> CheckResult:
    """A failing check whose every string field carries an HTML/script payload."""
    payload = "<script>alert('xss')</script>"
    return _check(
        "test:access_code#hostile", "output", "fail", f"Title {payload}", f"Message <img src=x onerror=alert(1)> {payload}",
        severity="major", diagnosis="stdout_mismatch", exercise_id="access_code", file=P_ACCESS,
        location=Location(file=f"{ROOT}/<b>evil</b>.py", line=1),
        evidence=Evidence(stdin="scooby\n", expected_stdout="Access denied.\n", actual_stdout=f"{payload}\n",
                          stdout_diff=text_diff("Access denied.\n", f"{payload}\n"),
                          exception=ExceptionInfo(type="<b>Boom</b>", message=payload, traceback=payload),
                          code=_excerpt(P_ACCESS, 1, [f'print("{payload}")'], 1)),
        fix=Fix(summary=payload, patch=f"--- a/x\n+++ b/x\n@@ -1 +1 @@\n-{payload}\n+print('ok')\n"),
    )


# ---- report --------------------------------------------------------------------------------------

def make_tree() -> list[TreeEntry]:
    return [
        TreeEntry(path=".gitignore", kind="file", size=24, status="ok", required=True),
        TreeEntry(path=f"{ROOT}/Fixme2.py", kind="file", size=180, status="misplaced", required=True,
                  note=f"expected {P_FIXME}"),
        TreeEntry(path=P_COUNTDOWN, kind="file", status="missing", required=False, bonus=True),
        TreeEntry(path=f"{ROOT}/flight_functions/__pycache__", kind="directory", status="parasite"),
        TreeEntry(path=f"{ROOT}/notes.py", kind="file", size=12, status="extra"),
        TreeEntry(path=P_KELVIN, kind="file", size=90, status="ok", required=True, git="tracked"),
    ]


def make_report(
    checks: list[CheckResult] | None = None,
    *,
    variant: str = "buggy",
    report_id: str = "analysis-1",
    number: int = 1,
    subject_id: str = "subject-1",
    project_id: str = "project-1",
    created_at: datetime | None = None,
    sandbox_mode: str = "docker",
    spec: PracticalSpec | None = None,
) -> AnalysisReport:
    spec = spec or make_spec()
    if checks is None:
        checks = buggy_checks(spec) if variant == "buggy" else passing_checks(spec)
    sandbox = SandboxInfo(
        mode=sandbox_mode, image="python:3.12-slim" if sandbox_mode == "docker" else None, python_version="3.12.7",
        limits={"memory": "256m", "cpus": 1, "pids": 128},
        warnings=[] if sandbox_mode == "docker" else ["Developer mode: student code runs with weaker isolation."],
    )
    git = GitInfo(is_repo=True, branch="main", head="a1b2c3d", last_commit_message="final version",
                  last_commit_date="2026-10-02T21:13:00+02:00", dirty=variant == "buggy",
                  modified=[P_SAFE] if variant == "buggy" else [], untracked=[P_LAUNCH] if variant == "buggy" else [])
    return AnalysisReport(
        id=report_id,
        number=number,
        created_at=created_at or datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
        duration_ms=4321.0,
        subject=SubjectSummary(id=subject_id, title=SUBJECT_TITLE, source_name="subject_demo.html", language="python",
                               parser="heuristic"),
        project=ProjectSummary(id=project_id, name=f"mysteryinc_{variant}", source_kind="demo",
                               path=f"demo/projects/mysteryinc_{variant}", detected_root="", file_count=14,
                               python_files=10, git=git),
        sandbox=sandbox,
        spec=spec,
        checks=checks,
        tree=make_tree() if variant == "buggy" else [],
        score=compute_score(checks, spec, spec_reviewed=True, sandbox_mode=sandbox_mode),
        pipeline_warnings=["Root detected automatically: MysteryInc/ found at the top level."] if variant == "buggy" else [],
    )
