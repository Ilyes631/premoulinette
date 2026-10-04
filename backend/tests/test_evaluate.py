import pytest

from premoulinette.compare.evaluate import EvalContext, evaluate_function, evaluate_import, evaluate_script
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo, ReturnInfo, StringLiteral
from premoulinette.results.models import Location, ValueSnapshot
from premoulinette.runner.models import JobResult, RawEvent, RawException
from premoulinette.spec.models import (
    BehaviorRule,
    ExerciseSpec,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    InteractionStep,
    Origin,
    Param,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
)
from premoulinette.testgen.generate import GeneratedFunctionTest, GeneratedScriptTest

ROOT = "MysteryInc/FirstLaunch"
SAFE = f"{ROOT}/flight_functions/safe_speed.py"
GRADE = f"{ROOT}/flight_functions/grade_landing.py"
AVG = f"{ROOT}/FIXME2.py"
MAXALT = f"{ROOT}/bonus/max_altitude.py"
LAUNCH = f"{ROOT}/launch_sequence.py"

SAFE_SRC = '''def is_safe(speed: int, limit: int) -> bool:
    if speed <= limit:
        return "True"
    return "False"
'''
GRADE_SRC = '''def landing_grade(vertical_speed: int) -> str:
    if vertical_speed <= 2:
        print("Perfect touchdown")
    elif vertical_speed <= 5:
        print("Hard landing")
    else:
        print("Crash!")
'''
LAUNCH_SRC = '''name = input("Pilot name: ")
fuel = int(input("Starting fuel: "))
print("Where's the Mystery Machine headed today?")
print("1 - Crystal Cove")
print("2 - The Old Mill")
print("3 - Spooky Swamp")
choice = input("Your choice: ")
places = {"1": ("Crystal Cove", 50), "2": ("The Old Mill", 120), "3": ("Spooky Swamp", 200)}
place, cost = places[choice]
if cost > fuel:
    print("Not enough fuel! The gang stays home.")
else:
    print("Destination: " + place)
    print("Fuel after the trip: " + str(fuel - cost))
    action = input("Set a trap or callect evidence? (trap/evidence) ")
    if action == "trap":
        print(name + " sets a trap at " + place + ". Zoinks!")
    else:
        print(name + " collects evidence at " + place + ". Jinkies!")
'''
PROMPTS = ["Pilot name: ", "Starting fuel: ", "Your choice: ", "Set a trap or collect evidence? (trap/evidence) "]
MENU = "Where's the Mystery Machine headed today?\n1 - Crystal Cove\n2 - The Old Mill\n3 - Spooky Swamp\n"


# ---- spec / context builders ------------------------------------------------------------------------


def fn_spec(name, params, ret, rules=(), tests=()):
    return FunctionSpec(
        signature=FunctionSignature(name=name, params=[Param(name=n, annotation=a) for n, a in params], return_annotation=ret),
        rules=[BehaviorRule(when=w, returns=r) for w, r in rules],
        tests=list(tests),
    )


def ftest(test_id, function, args, expected=None, provenance="explicit", **extra):
    return FunctionTest(id=test_id, function=function, args=args, expected_return=expected,
                        origin=Origin(provenance=provenance), **extra)


def session(n, *steps):
    return ScriptTest(id=f"launch_sequence#session{n}", steps=[InteractionStep(kind=k, text=t) for k, t in steps])


SESSIONS = [
    session(1, ("output", "Pilot name: "), ("input", "Camille"), ("output", "Starting fuel: "), ("input", "400"),
            ("output", MENU + "Your choice: "), ("input", "2"),
            ("output", "Destination: The Old Mill\nFuel after the trip: 280\n" + PROMPTS[3]), ("input", "trap"),
            ("output", "Camille sets a trap at The Old Mill. Zoinks!\n")),
    session(2, ("output", "Pilot name: "), ("input", "Fred"), ("output", "Starting fuel: "), ("input", "100"),
            ("output", MENU + "Your choice: "), ("input", "3"), ("output", "Not enough fuel! The gang stays home.\n")),
    session(3, ("output", "Pilot name: "), ("input", "Velma"), ("output", "Starting fuel: "), ("input", "250"),
            ("output", MENU + "Your choice: "), ("input", "1"),
            ("output", "Destination: Crystal Cove\nFuel after the trip: 200\n" + PROMPTS[3]), ("input", "evidence"),
            ("output", "Velma collects evidence at Crystal Cove. Jinkies!\n")),
]


def build_spec():
    return PracticalSpec(exercises=[
        ExerciseSpec(id="safe_speed", title="Safe speed", file_path=SAFE, functions=[fn_spec(
            "is_safe", [("speed", "int"), ("limit", "int")], "bool", rules=[("speed <= limit", "True"), (None, "False")],
            tests=[ftest("is_safe#ex1", "is_safe", ["200", "250"], "True"),
                   ftest("is_safe#ex2", "is_safe", ["300", "250"], "False")])]),
        ExerciseSpec(id="grade_landing", title="Landing grade", file_path=GRADE, functions=[fn_spec(
            "landing_grade", [("vertical_speed", "int")], "str",
            tests=[ftest("landing_grade#ex2", "landing_grade", ["4"], "'Hard landing'")])]),
        ExerciseSpec(id="FIXME2", title="FIXME", file_path=AVG, functions=[fn_spec(
            "average_speed", [("distance", "float"), ("hours", "float")], "float",
            tests=[ftest("average_speed#ex1", "average_speed", ["150.0", "2.0"], "75.0")])]),
        ExerciseSpec(id="max_altitude", title="Max altitude", bonus=True, file_path=MAXALT, functions=[fn_spec(
            "max_altitude", [("a", "int"), ("b", "int"), ("c", "int")], "int",
            tests=[ftest("max_altitude#ex1", "max_altitude", ["1", "5", "3"], "5")])]),
        ExerciseSpec(id="launch_sequence", title="Launch", kind="script", file_path=LAUNCH,
                     script=ScriptSpec(prompts=list(PROMPTS), tests=list(SESSIONS))),
    ])


def module(path, functions=(), strings=()):
    return ModuleInfo(path=path, ok=True, functions=list(functions), strings=list(strings))


MODULES = {
    SAFE: module(SAFE, [FunctionInfo(
        name="is_safe", line=1, end_line=4, has_value_return=True,
        returns=[ReturnInfo(line=3, value_src="'True'", value_kind="constant", constant_type="str"),
                 ReturnInfo(line=4, value_src="'False'", value_kind="constant", constant_type="str")])]),
    GRADE: module(GRADE, [FunctionInfo(name="landing_grade", line=1, end_line=7, prints=[3, 5, 7])]),
    AVG: module(AVG, [FunctionInfo(name="average_speed", line=1, end_line=4, has_value_return=True)]),
    MAXALT: module(MAXALT, [FunctionInfo(name="max_altitude", line=1, end_line=6, has_value_return=True)]),
    LAUNCH: module(LAUNCH, strings=[
        StringLiteral(value="Set a trap or callect evidence? (trap/evidence) ", line=15, end_line=15, col=19, end_col=70,
                      in_call="input"),
    ]),
}


def make_ctx(**overrides):
    values = {
        "spec": build_spec(), "modules": MODULES, "file_map": {p: p for p in (SAFE, GRADE, AVG, MAXALT, LAUNCH)},
        "sources": {SAFE: SAFE_SRC, GRADE: GRADE_SRC, LAUNCH: LAUNCH_SRC},
    }
    values.update(overrides)
    return EvalContext(**values)


def gen_fn(test, exercise_id, category="explicit_tests", rule=None):
    return GeneratedFunctionTest(test=test, exercise_id=exercise_id, category=category, rule=rule)


def call_ok(test_id, value_repr, type_name, stdout="", events=()):
    return JobResult(id=test_id, kind="function", status="ok", return_repr=value_repr, return_type=type_name,
                     return_literal=True, stdout=stdout, events=list(events))


IS_SAFE_EX1 = ftest("is_safe#ex1", "is_safe", ["200", "250"], "True")


# ---- function tests: product brief ------------------------------------------------------------------


def test_is_safe_returning_string_true():
    res = call_ok("is_safe#ex1", "'True'", "str")
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed", rule="speed <= limit → True"), res, make_ctx())
    assert check.id == "test:is_safe#ex1" and check.category == "explicit_tests"
    assert check.status == "fail" and check.severity == "major" and check.mandatory and not check.bonus
    assert check.diagnosis == "str_instead_of_bool"
    assert check.evidence.expected_value == ValueSnapshot(repr="True", type="bool")
    assert check.evidence.actual_value == ValueSnapshot(repr="'True'", type="str")
    assert check.evidence.call == "is_safe(200, 250)" and check.evidence.rule == "speed <= limit → True"
    assert check.exercise_id == "safe_speed" and check.function == "is_safe" and check.test_id == "is_safe#ex1"
    assert check.file == SAFE
    assert check.location == Location(file=SAFE, line=3)            # the `return "True"` line
    assert check.evidence.code is not None and check.evidence.code.highlight == [3]
    assert check.evidence.code.lines[2] == '        return "True"'


def test_correct_value_passes_without_diagnosis():
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), call_ok("is_safe#ex1", "True", "bool"), make_ctx())
    assert check.status == "pass" and check.severity is None and check.diagnosis is None and check.mandatory


def test_prints_instead_of_returns_points_at_the_print_line():
    test = ftest("landing_grade#ex2", "landing_grade", ["4"], "'Hard landing'")
    res = call_ok("landing_grade#ex2", "None", "NoneType", stdout="Hard landing\n",
                  events=[RawEvent(kind="output", text="Hard landing\n", file=GRADE, line=5)])
    check = evaluate_function(gen_fn(test, "grade_landing"), res, make_ctx())
    assert check.status == "fail" and check.severity == "major"
    assert check.diagnosis == "prints_instead_of_returns"
    assert check.location == Location(file=GRADE, line=5)
    assert check.evidence.code.highlight == [5]
    assert check.evidence.actual_stdout == "Hard landing\n"


def test_returns_none_without_printing():
    test = ftest("landing_grade#ex2", "landing_grade", ["4"], "'Hard landing'")
    check = evaluate_function(gen_fn(test, "grade_landing"), call_ok("landing_grade#ex2", "None", "NoneType"), make_ctx())
    assert check.diagnosis == "returns_none" and check.status == "fail" and check.severity == "major"


def test_float_tolerance_passes():
    test = ftest("average_speed#ex1", "average_speed", ["150.0", "2.0"], "75.0")
    res = call_ok("average_speed#ex1", "75.00000000000001", "float")
    check = evaluate_function(gen_fn(test, "FIXME2"), res, make_ctx())
    assert check.status == "pass" and check.evidence.details["verdict"] == "float_close"


def test_int_instead_of_float_is_a_mandatory_warning():
    test = ftest("average_speed#ex1", "average_speed", ["150.0", "2.0"], "75.0")
    check = evaluate_function(gen_fn(test, "FIXME2"), call_ok("average_speed#ex1", "75", "int"), make_ctx())
    assert check.status == "warning" and check.severity == "minor" and check.mandatory
    assert check.diagnosis == "int_instead_of_float"


def test_bool_versus_int_is_a_wrong_type():
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), call_ok("is_safe#ex1", "1", "int"), make_ctx())
    assert check.status == "fail" and check.diagnosis == "wrong_type" and check.severity == "major"


def test_number_returned_as_string():
    test = ftest("average_speed#ex1", "average_speed", ["150.0", "2.0"], "75.0")
    check = evaluate_function(gen_fn(test, "FIXME2"), call_ok("average_speed#ex1", "'75.0'", "str"), make_ctx())
    assert check.status == "fail" and check.diagnosis == "number_as_str"


def test_wrong_string_typo_is_a_minor_fail_with_value_diff():
    test = ftest("landing_grade#ex2", "landing_grade", ["4"], "'Hard landing'")
    check = evaluate_function(gen_fn(test, "grade_landing"), call_ok("landing_grade#ex2", "'Hard lending'", "str"),
                              make_ctx())
    assert check.status == "fail" and check.severity == "minor" and check.diagnosis == "wrong_string"
    assert check.evidence.value_diff is not None and "typo" in check.evidence.value_diff.kinds


@pytest.mark.parametrize(("status", "diagnosis", "extra"), [
    ("timeout", "timeout", {}),
    ("exception", "exception", {"exception": RawException(type="ZeroDivisionError", message="division by zero",
                                                          file=AVG, line=3)}),
    ("import_error", "import_crash", {"exception": RawException(type="NameError", message="name 'x' is not defined",
                                                             file=AVG, line=7)}),
    ("syntax_error", "syntax_error", {"exception": RawException(type="SyntaxError", message="invalid syntax",
                                                             file=AVG, line=2)}),
    ("exception", "blocked_syscall", {"blocked_syscalls": ["socket.connect"],
                                      "exception": RawException(type="PermissionError", message="blocked")}),
    ("output_limit", "output_limit", {"truncated": True}),
])
def test_runtime_failures_are_critical(status, diagnosis, extra):
    test = ftest("average_speed#ex1", "average_speed", ["150.0", "2.0"], "75.0")
    res = JobResult(id="average_speed#ex1", kind="function", status=status, **extra)
    check = evaluate_function(gen_fn(test, "FIXME2"), res, make_ctx())
    assert check.status == "fail" and check.severity == "critical" and check.diagnosis == diagnosis
    assert check.mandatory
    exc = extra.get("exception")
    if exc is not None and exc.file:
        assert check.location == Location(file=exc.file, line=exc.line)
        assert check.evidence.exception.type == exc.type
    assert check.evidence.timed_out == (status == "timeout")


def test_unexpected_stdout_turns_a_pass_into_a_warning():
    res = call_ok("is_safe#ex1", "True", "bool", stdout="debug\n",
                  events=[RawEvent(kind="output", text="debug\n", file=SAFE, line=2)])
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), res, make_ctx())
    assert check.status == "warning" and check.diagnosis == "unexpected_stdout" and "unexpected_stdout" in check.tags
    assert check.location == Location(file=SAFE, line=2)


def test_expected_exception():
    test = ftest("is_safe#ex1", "is_safe", ["-1", "250"], None, expected_exception="ValueError")
    raised = JobResult(id="is_safe#ex1", kind="function", status="exception",
                       exception=RawException(type="ValueError", message="negative", file=SAFE, line=2))
    assert evaluate_function(gen_fn(test, "safe_speed"), raised, make_ctx()).status == "pass"
    returned = evaluate_function(gen_fn(test, "safe_speed"), call_ok("is_safe#ex1", "True", "bool"), make_ctx())
    assert returned.status == "fail" and returned.severity == "major"


# ---- function tests: status policy ------------------------------------------------------------------


def test_heuristic_failure_is_a_non_mandatory_warning():
    test = ftest("is_safe#heur1", "is_safe", ["0", "250"], "True", provenance="heuristic")
    check = evaluate_function(gen_fn(test, "safe_speed", category="heuristic_tests"),
                              call_ok("is_safe#heur1", "'True'", "str"), make_ctx())
    assert check.category == "heuristic_tests"
    assert check.status == "warning" and not check.mandatory and check.severity == "minor"
    assert check.diagnosis == "str_instead_of_bool"
    passing = evaluate_function(gen_fn(test, "safe_speed", category="heuristic_tests"),
                                call_ok("is_safe#heur1", "True", "bool"), make_ctx())
    assert passing.status == "pass" and not passing.mandatory


def test_derived_failure_is_a_mandatory_fail():
    test = ftest("is_safe#derived1", "is_safe", ["250", "250"], "True", provenance="derived")
    check = evaluate_function(gen_fn(test, "safe_speed", category="derived_tests"),
                              call_ok("is_safe#derived1", "False", "bool"), make_ctx())
    assert check.category == "derived_tests" and check.status == "fail" and check.mandatory
    assert check.diagnosis == "wrong_value" and check.severity == "major"


def test_bonus_failure_has_status_bonus():
    test = ftest("max_altitude#ex1", "max_altitude", ["1", "5", "3"], "5")
    check = evaluate_function(gen_fn(test, "max_altitude"), call_ok("max_altitude#ex1", "3", "int"), make_ctx())
    assert check.status == "bonus" and check.bonus and not check.mandatory
    assert check.diagnosis == "wrong_value"
    ok = evaluate_function(gen_fn(test, "max_altitude"), call_ok("max_altitude#ex1", "5", "int"), make_ctx())
    assert ok.status == "pass" and ok.bonus and not ok.mandatory


def test_blocked_test_is_skipped_with_blocked_by():
    ctx = make_ctx(blocked={SAFE: f"structure:file:{SAFE}"})
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), None, ctx)
    assert check.status == "skipped" and check.blocked_by == f"structure:file:{SAFE}"
    assert check.mandatory and check.severity is None
    assert "blocked by structure:file:" in check.message


def test_missing_function_blocks_the_test():
    ctx = make_ctx(modules={**MODULES, SAFE: module(SAFE)})
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), None, ctx)
    assert check.status == "skipped" and check.blocked_by == "function:safe_speed:is_safe" and check.mandatory


def test_function_level_blocker_and_harness_error():
    ctx = make_ctx(blocked={f"{SAFE}::is_safe": "signature:safe_speed:is_safe"})
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), call_ok("is_safe#ex1", "True", "bool"), ctx)
    assert check.status == "skipped" and check.blocked_by == "signature:safe_speed:is_safe"
    broken = JobResult(id="is_safe#ex1", kind="function", status="harness_error", harness_error="bad plan")
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), broken, make_ctx())
    assert check.status == "skipped" and "harness error" in check.message


def test_misplaced_file_uses_the_actual_path_for_locations():
    actual = f"{ROOT}/safe_speed.py"
    moved = MODULES[SAFE].model_copy(update={"path": actual})
    ctx = make_ctx(modules={actual: moved}, file_map={SAFE: actual}, sources={actual: SAFE_SRC})
    check = evaluate_function(gen_fn(IS_SAFE_EX1, "safe_speed"), call_ok("is_safe#ex1", "'True'", "str"), ctx)
    assert check.location == Location(file=actual, line=3)
    assert check.evidence.code.file == actual


# ---- script sessions -----------------------------------------------------------------------------------


class _EOF(Exception):
    pass


class FakeIO:
    """Mimics the harness: print/input events with the source line, input() not echoed, EOFError."""

    def __init__(self, stdin):
        self.lines = stdin.split("\n")[:-1] if stdin else []
        self.stdout = ""
        self.events = []

    def print(self, text, line):
        self.stdout += text + "\n"
        self.events.append(RawEvent(kind="output", text=text + "\n", file=LAUNCH, line=line))

    def input(self, prompt, line):
        if prompt:
            self.stdout += prompt
            self.events.append(RawEvent(kind="output", text=prompt, file=LAUNCH, line=line))
        if not self.lines:
            raise _EOF(line)
        value = self.lines.pop(0)
        self.events.append(RawEvent(kind="input", text=value, file=LAUNCH, line=line))
        return value


def launch_program(io, *, trap_prompt="Set a trap or callect evidence? (trap/evidence) ", skip_swamp=False,
                   debug=False, choice_prompt="Your choice: ", menu_prompt_printed=False, extra_input=False):
    name = io.input("Pilot name: ", 1)
    fuel = int(io.input("Starting fuel: ", 2))
    io.print("Where's the Mystery Machine headed today?", 3)
    io.print("1 - Crystal Cove", 4)
    io.print("2 - The Old Mill", 5)
    if not skip_swamp:
        io.print("3 - Spooky Swamp", 6)
    if menu_prompt_printed:
        io.print(choice_prompt.rstrip(), 7)
        choice = io.input("", 7)
    else:
        choice = io.input(choice_prompt, 7)
    place, cost = {"1": ("Crystal Cove", 50), "2": ("The Old Mill", 120), "3": ("Spooky Swamp", 200)}[choice]
    if cost > fuel:
        io.print("Not enough fuel! The gang stays home.", 11)
        return
    io.print("Destination: " + place, 13)
    if debug:
        io.print(f"DEBUG fuel={fuel}", 14)
    io.print("Fuel after the trip: " + str(fuel - cost), 14)
    if extra_input:
        io.input("Confirm? ", 15)
    action = io.input(trap_prompt, 15)
    if action == "trap":
        io.print(name + " sets a trap at " + place + ". Zoinks!", 17)
    else:
        io.print(name + " collects evidence at " + place + ". Jinkies!", 19)


def run_launch(test, **behaviour):
    io = FakeIO(test.stdin)
    try:
        launch_program(io, **behaviour)
    except _EOF as eof:
        return JobResult(id=test.id, kind="script", status="exception", stdout=io.stdout, events=io.events, exit_code=1,
                         exception=RawException(type="EOFError", message="EOF when reading a line",
                                                file=LAUNCH, line=eof.args[0]))
    return JobResult(id=test.id, kind="script", status="ok", stdout=io.stdout, events=io.events, exit_code=0)


def gen_script(test):
    return GeneratedScriptTest(test=test, exercise_id="launch_sequence", category="output")


def run_all_sessions(ctx, **behaviour):
    checks = []
    for test in SESSIONS:
        checks.extend(evaluate_script(gen_script(test), run_launch(test, **behaviour), ctx))
    return {c.id: c for c in checks}


def test_correct_program_passes_every_session_and_prompt():
    checks = run_all_sessions(make_ctx(), trap_prompt=PROMPTS[3])
    assert sorted(checks) == sorted([f"test:launch_sequence#session{n}" for n in (1, 2, 3)]
                                    + [f"prompt:launch_sequence:{n}" for n in (1, 2, 3, 4)])
    assert all(c.status == "pass" and c.mandatory for c in checks.values())
    assert checks["test:launch_sequence#session1"].category == "output"
    assert checks["prompt:launch_sequence:4"].location == Location(file=LAUNCH, line=15)


def test_prompt_typo_in_stdout_is_mapped_to_the_input_call():
    test = SESSIONS[0]
    (check,) = evaluate_script(gen_script(test), run_launch(test), make_ctx())   # session 1 of 3: no prompt checks yet
    assert check.id == "test:launch_sequence#session1"
    assert check.status == "fail" and check.severity == "minor" and check.diagnosis == "stdout_mismatch"
    diff = check.evidence.stdout_diff
    (line,) = [ln for ln in diff.lines if ln.op != "equal"]
    assert line.op == "changed" and line.expected_lineno == 7     # prompts are not followed by a newline
    assert line.hints[0] == "typo: 'o' → 'a' (col 16)"
    assert line.source == Location(file=LAUNCH, line=15)             # the input() call, not the following print
    assert check.location == Location(file=LAUNCH, line=15)
    assert "line 15" in check.message
    assert check.evidence.code is not None and 15 in check.evidence.code.highlight
    equal = [ln for ln in diff.lines if ln.op == "equal"]
    assert equal[0].expected.startswith("Pilot name: Starting fuel: Where's")
    assert equal[0].source == Location(file=LAUNCH, line=1)          # written first by input("Pilot name: ")
    assert equal[1].expected == "1 - Crystal Cove" and equal[1].source == Location(file=LAUNCH, line=4)
    assert check.evidence.stdin == "Camille\n400\n2\ntrap\n" and check.evidence.transcript


def test_prompt_checks_from_input_events():
    checks = run_all_sessions(make_ctx())
    prompts = [checks[f"prompt:launch_sequence:{n}"] for n in (1, 2, 3, 4)]
    assert [c.status for c in prompts] == ["pass", "pass", "pass", "fail"]
    bad = prompts[3]
    assert bad.category == "output" and bad.diagnosis == "prompt_mismatch" and bad.severity == "minor" and bad.mandatory
    assert bad.location == Location(file=LAUNCH, line=15)
    assert bad.evidence.value_diff is not None and "typo" in bad.evidence.value_diff.kinds
    assert bad.evidence.expected_value == ValueSnapshot(repr=repr(PROMPTS[3]), type="str")
    assert bad.evidence.details["actual_prompt"] == "Set a trap or callect evidence? (trap/evidence) "
    assert bad.evidence.details["session"] == "launch_sequence#session1"
    assert "typo: 'o' → 'a' (col 16)" in bad.message
    assert prompts[2].location == Location(file=LAUNCH, line=7)


def test_prompt_checks_are_emitted_once_after_the_last_session():
    ctx = make_ctx()
    counts = [len(evaluate_script(gen_script(t), run_launch(t), ctx)) for t in SESSIONS]
    assert counts == [1, 1, 1 + len(PROMPTS)]


def test_prompt_checks_use_ctx_results_when_sessions_are_evaluated_out_of_order():
    results = {t.id: run_launch(t) for t in SESSIONS}
    ctx = make_ctx(results=results)
    checks = evaluate_script(gen_script(SESSIONS[2]), results[SESSIONS[2].id], ctx)
    assert [c.id for c in checks][1:] == [f"prompt:launch_sequence:{n}" for n in (1, 2, 3, 4)]
    assert checks[-1].evidence.details["session"] == "launch_sequence#session1"


def test_missing_trailing_space_in_prompt():
    checks = run_all_sessions(make_ctx(), trap_prompt=PROMPTS[3], choice_prompt="Your choice:")
    bad = checks["prompt:launch_sequence:3"]
    assert bad.status == "fail" and bad.diagnosis == "prompt_mismatch" and bad.severity == "minor"
    assert "missing trailing space" in bad.message


def test_prompt_printed_on_its_own_line():
    checks = run_all_sessions(make_ctx(), trap_prompt=PROMPTS[3], menu_prompt_printed=True)
    bad = checks["prompt:launch_sequence:3"]
    assert bad.diagnosis == "prompt_mismatch" and bad.status == "fail"
    assert "own line" in bad.message
    assert bad.location == Location(file=LAUNCH, line=7)


def test_missing_line_and_extra_line_are_aligned():
    test = SESSIONS[0]
    check = evaluate_script(gen_script(test), run_launch(test, trap_prompt=PROMPTS[3], skip_swamp=True, debug=True),
                            make_ctx())[0]
    assert check.status == "fail" and check.severity == "major" and check.diagnosis == "stdout_mismatch"
    rows = [(ln.op, ln.expected_lineno, ln.actual_lineno) for ln in check.evidence.stdout_diff.lines if ln.op != "equal"]
    assert rows == [("missing", 4, None), ("extra", None, 5)]
    extra = next(ln for ln in check.evidence.stdout_diff.lines if ln.op == "extra")
    assert extra.actual == "DEBUG fuel=400" and extra.source == Location(file=LAUNCH, line=14)
    assert check.location is None or check.location.file == LAUNCH
    assert "3 - Spooky Swamp" in check.message


def test_eof_error_when_the_program_reads_too_much():
    test = SESSIONS[0]
    check = evaluate_script(gen_script(test), run_launch(test, trap_prompt=PROMPTS[3], extra_input=True), make_ctx())[0]
    assert check.status == "fail" and check.severity == "critical" and check.diagnosis == "eof_error"
    assert check.location == Location(file=LAUNCH, line=15)
    assert "'Set a trap or collect evidence? (trap/evidence) '" in check.message


def test_script_crash_timeout_and_exit_code():
    test = SESSIONS[1]
    crash = JobResult(id=test.id, kind="script", status="exception", stdout="Pilot name: ", exit_code=1,
                      exception=RawException(type="ValueError", message="invalid literal for int()", file=LAUNCH, line=2))
    check = evaluate_script(gen_script(test), crash, make_ctx())[0]
    assert check.diagnosis == "script_crash" and check.severity == "critical" and check.status == "fail"
    assert check.location == Location(file=LAUNCH, line=2)

    timeout = JobResult(id=test.id, kind="script", status="timeout", stdout="")
    check = evaluate_script(gen_script(test), timeout, make_ctx())[0]
    assert check.diagnosis == "timeout" and check.severity == "critical" and check.evidence.timed_out

    exited = run_launch(test, trap_prompt=PROMPTS[3]).model_copy(update={"exit_code": 3})
    check = evaluate_script(gen_script(test), exited, make_ctx())[0]
    assert check.diagnosis == "exit_code" and check.status == "fail"


def test_blocked_script_and_prompt_checks_are_skipped():
    ctx = make_ctx(blocked={LAUNCH: f"syntax:{LAUNCH}"})
    checks = []
    for test in SESSIONS:
        checks.extend(evaluate_script(gen_script(test), None, ctx))
    assert len(checks) == 3 + len(PROMPTS)
    assert all(c.status == "skipped" and c.blocked_by == f"syntax:{LAUNCH}" and c.mandatory for c in checks)


def test_missing_prompt_when_no_session_asks_for_it():
    spec = build_spec()
    spec.exercises[4].script.prompts = PROMPTS + ["Mission rating: "]
    ctx = make_ctx(spec=spec)
    checks = {}
    for test in SESSIONS:
        for c in evaluate_script(gen_script(test), run_launch(test, trap_prompt=PROMPTS[3]), ctx):
            checks[c.id] = c
    assert [checks[f"prompt:launch_sequence:{n}"].status for n in (1, 2, 3, 4)] == ["pass"] * 4
    missing = checks["prompt:launch_sequence:5"]
    assert missing.status == "fail" and missing.severity == "major" and missing.diagnosis == "missing_prompt"
    assert "never asked for input 5" in missing.message


def test_wrong_input_order_is_a_prompt_mismatch():
    spec = build_spec()
    spec.exercises[4].script.prompts = [PROMPTS[1], PROMPTS[0], PROMPTS[2], PROMPTS[3]]
    checks = run_all_sessions(make_ctx(spec=spec), trap_prompt=PROMPTS[3])
    assert checks["prompt:launch_sequence:1"].diagnosis == "prompt_mismatch"
    assert checks["prompt:launch_sequence:1"].severity == "major"
    assert checks["prompt:launch_sequence:3"].status == "pass"


# ---- import side effects --------------------------------------------------------------------------------


def import_result(**fields):
    return JobResult(id="import:safe_speed", kind="import", status=fields.pop("status", "ok"), exit_code=0, **fields)


def test_import_clean_prints_and_waits_for_input():
    ctx = make_ctx()
    clean = evaluate_import("safe_speed", import_result(), ctx)
    assert clean.id == "import_effects:safe_speed" and clean.status == "pass" and clean.category == "runtime"

    printed = import_result(stdout="testing\n", import_stdout="testing\n",
                            events=[RawEvent(kind="output", text="testing\n", file=SAFE, line=6)])
    check = evaluate_import("safe_speed", printed, ctx)
    assert check.status == "warning" and check.severity == "major" and check.diagnosis == "import_side_effects"
    assert check.location == Location(file=SAFE, line=6)

    waits = import_result(status="exception", stdout="Speed? ",
                          events=[RawEvent(kind="output", text="Speed? ", file=SAFE, line=7)],
                          exception=RawException(type="EOFError", message="EOF when reading a line", file=SAFE, line=7))
    check = evaluate_import("safe_speed", waits, ctx)
    assert check.diagnosis == "import_waits_input" and check.location == Location(file=SAFE, line=7)

    crash = import_result(status="exception",
                          exception=RawException(type="NameError", message="name 'x' is not defined", file=SAFE, line=8))
    check = evaluate_import("safe_speed", crash, ctx)
    assert check.diagnosis == "import_crash" and check.location == Location(file=SAFE, line=8)


def test_import_check_ignores_scripts_blocked_and_syntax_errors():
    ctx = make_ctx(blocked={GRADE: f"structure:file:{GRADE}"})
    assert evaluate_import("launch_sequence", import_result(), ctx) is None
    assert evaluate_import("grade_landing", import_result(), ctx) is None
    assert evaluate_import("safe_speed", import_result(status="syntax_error"), ctx) is None
    assert evaluate_import("unknown", import_result(), ctx) is None
