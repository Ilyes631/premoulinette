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
from premoulinette.testgen.generate import (
    AI_DERIVED_CONFIDENCE,
    DERIVED_CONFIDENCE,
    HEURISTIC_CONFIDENCE,
    MAX_HEURISTIC_PER_FUNCTION,
    generate_tests,
)
from premoulinette.testgen.oracle import literal, safe_eval

MISSION_CLOCK_REF = 'f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"'


def make_fn(name, params, ret, rules=(), reference=None, tests=(), rule_provenance="explicit"):
    return FunctionSpec(
        signature=FunctionSignature(
            name=name, params=[Param(name=n, annotation=a) for n, a in params], return_annotation=ret
        ),
        rules=[BehaviorRule(when=w, returns=r, origin=Origin(provenance=rule_provenance)) for w, r in rules],
        reference=reference,
        tests=[FunctionTest(id=f"{name}#ex{i + 1}", function=name, args=list(a), expected_return=e)
               for i, (a, e) in enumerate(tests)],
    )


def exercise(ex_id, *functions, bonus=False, script=None, kind="functions"):
    return ExerciseSpec(id=ex_id, title=ex_id, kind=kind, bonus=bonus, file_path=f"MysteryInc/FirstLaunch/{ex_id}.py",
                        functions=list(functions), script=script)


def demo_spec() -> PracticalSpec:
    """The function exercises of demo/subject_demo.html, as the heuristic parser extracts them."""
    return PracticalSpec(exercises=[
        exercise("kelvin", make_fn("to_kelvin", [("celsius", "float")], "float", reference="celsius + 273.15",
                                   tests=[(["0"], "273.15")])),
        exercise("safe_speed", make_fn(
            "is_safe", [("speed", "int"), ("limit", "int")], "bool",
            rules=[("speed <= limit", "True"), (None, "False")],
            tests=[(["200", "250"], "True"), (["300", "250"], "False")])),
        exercise("grade_landing", make_fn(
            "landing_grade", [("vertical_speed", "int")], "str",
            rules=[("vertical_speed <= 2", "'Perfect touchdown'"), ("2 < vertical_speed <= 5", "'Hard landing'"),
                   ("vertical_speed > 5", "'Crash!'")],
            tests=[(["1"], "'Perfect touchdown'"), (["4"], "'Hard landing'"), (["9"], "'Crash!'")])),
        exercise("mission_clock", make_fn(
            "mission_clock", [("seconds", "int")], "str", reference=MISSION_CLOCK_REF,
            tests=[(["3725"], None), (["0"], "'00:00:00'")])),
        exercise("FIXME2", make_fn(
            "average_speed", [("distance", "float"), ("hours", "float")], "float",
            rules=[("hours == 0", "0.0"), (None, "distance / hours")],
            tests=[(["150.0", "2.0"], "75.0"), (["10.0", "0.0"], "0.0")])),
    ])


def by_function(gens, name):
    return [g for g in gens if g.test.function == name]


def args_of(gens):
    return [tuple(literal(a) for a in g.test.args) for g in gens]


# ---- explicit tests -------------------------------------------------------------------------------


def test_explicit_tests_are_copied_and_missing_expected_values_filled_by_the_oracle():
    spec = demo_spec()
    before = spec.model_dump()
    fns, scripts = generate_tests(spec)
    assert scripts == []
    clock = {g.test.id: g for g in by_function(fns, "mission_clock")}
    ex1 = clock["mission_clock#ex1"]
    assert ex1.category == "explicit_tests" and ex1.exercise_id == "mission_clock"
    assert ex1.test.expected_return == "'01:02:05'"          # f-string reference with format spec
    assert ex1.rule == f"returns {MISSION_CLOCK_REF}"
    assert clock["mission_clock#ex2"].test.expected_return == "'00:00:00'"
    assert spec.model_dump() == before                         # the spec is never mutated
    assert spec.exercises[3].functions[0].tests[0].expected_return is None


def test_oracle_fstring_with_format_spec_mission_clock():
    assert safe_eval(MISSION_CLOCK_REF, {"seconds": 3725}) == "01:02:05"


def test_explicit_expected_value_is_never_overwritten_by_the_oracle():
    fn = make_fn("is_safe", [("speed", "int"), ("limit", "int")], "bool",
                 rules=[("speed <= limit", "True"), (None, "False")], tests=[(["200", "250"], "False")])
    spec = PracticalSpec(exercises=[exercise("safe_speed", fn)])
    explicit = [g for g in generate_tests(spec)[0] if g.category == "explicit_tests"]
    assert [g.test.expected_return for g in explicit] == ["False"]
    assert explicit[0].test.origin.provenance == "explicit"


def test_explicit_expected_exception_from_a_raises_rule():
    fn = FunctionSpec(
        signature=FunctionSignature(name="sqrt_int", params=[Param(name="x", annotation="int")], return_annotation="int"),
        rules=[BehaviorRule(when="x < 0", raises="ValueError"), BehaviorRule(returns="x // 2")],
        tests=[FunctionTest(id="sqrt_int#ex1", function="sqrt_int", args=["-4"])],
    )
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("sq", fn)]))
    ex1 = next(g for g in fns if g.test.id == "sqrt_int#ex1")
    assert ex1.test.expected_exception == "ValueError" and ex1.test.expected_return is None
    assert ex1.rule == "x < 0 → raises ValueError"


# ---- derived tests --------------------------------------------------------------------------------


def test_landing_grade_derived_boundaries_from_rules():
    fns, _ = generate_tests(demo_spec())
    derived = [g for g in by_function(fns, "landing_grade") if g.category == "derived_tests"]
    assert [g.test.id for g in derived] == [f"landing_grade#derived{n}" for n in range(1, 5)]
    assert [(g.test.args, g.test.expected_return) for g in derived] == [
        (["2"], "'Perfect touchdown'"), (["3"], "'Hard landing'"),
        (["5"], "'Hard landing'"), (["6"], "'Crash!'"),
    ]
    for g in derived:
        origin = g.test.origin
        assert origin.provenance == "derived" and origin.confidence == DERIVED_CONFIDENCE
        assert origin.note and origin.note.startswith("Boundary of rule '")
        assert g.exercise_id == "grade_landing" and g.rule and "→" in g.rule
    assert derived[2].rule == "2 < vertical_speed <= 5 → 'Hard landing'"


def test_is_safe_derived_boundary_speed_equals_limit():
    fns, _ = generate_tests(demo_spec())
    derived = [g for g in by_function(fns, "is_safe") if g.category == "derived_tests"]
    first = derived[0]
    assert first.test.id == "is_safe#derived1"
    assert first.test.args == ["250", "250"] and first.test.expected_return == "True"
    assert "speed == limit" in (first.test.origin.note or "")
    assert [(g.test.args, g.test.expected_return) for g in derived[1:]] == [
        (["251", "250"], "False"), (["249", "250"], "True"),
    ]


def test_derived_and_heuristic_never_duplicate_a_call_and_ids_are_unique():
    fns, _ = generate_tests(demo_spec())
    ids = [g.test.id for g in fns]
    assert len(ids) == len(set(ids))
    for name in ("to_kelvin", "is_safe", "landing_grade", "mission_clock", "average_speed"):
        gens = by_function(fns, name)
        calls = args_of(gens)
        assert len(calls) == len(set(calls)), name
        explicit = set(args_of([g for g in gens if g.category == "explicit_tests"]))
        assert not explicit & set(args_of([g for g in gens if g.category != "explicit_tests"])), name


def test_float_rules_derive_float_boundaries():
    fns, _ = generate_tests(demo_spec())
    derived = [g for g in by_function(fns, "average_speed") if g.category == "derived_tests"]
    assert [(g.test.args, g.test.expected_return) for g in derived] == [
        (["150.0", "0.0"], "0.0"), (["150.0", "0.5"], "300.0"), (["150.0", "-0.5"], "-300.0"),
    ]


def test_ai_extracted_rules_give_low_confidence_derived_tests_and_heuristic_rules_are_ignored():
    ai = make_fn("is_safe", [("speed", "int"), ("limit", "int")], "bool",
                 rules=[("speed <= limit", "True"), (None, "False")], tests=[(["200", "250"], "True")],
                 rule_provenance="ai_extracted")
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("safe_speed", ai)]))
    derived = [g for g in fns if g.category == "derived_tests"]
    assert derived and all(g.test.origin.confidence == AI_DERIVED_CONFIDENCE for g in derived)
    assert "review" in (derived[0].test.origin.note or "")

    guessed = make_fn("is_safe", [("speed", "int"), ("limit", "int")], "bool",
                      rules=[("speed <= limit", "True"), (None, "False")], tests=[(["200", "250"], "True")],
                      rule_provenance="heuristic")
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("safe_speed", guessed)]))
    assert not [g for g in fns if g.category == "derived_tests"]


def test_generated_ids_skip_ids_already_used_in_the_spec():
    fn = make_fn("is_safe", [("speed", "int"), ("limit", "int")], "bool",
                 rules=[("speed <= limit", "True"), (None, "False")], tests=[(["200", "250"], "True")])
    fn.tests.append(FunctionTest(id="is_safe#derived1", function="is_safe", args=["1", "2"], expected_return="True",
                                 origin=Origin(provenance="user")))
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("safe_speed", fn)]))
    derived_ids = [g.test.id for g in fns if g.category == "derived_tests"]
    assert "is_safe#derived1" not in derived_ids and derived_ids[0] == "is_safe#derived2"
    user = next(g for g in fns if g.test.id == "is_safe#derived1")
    assert user.category == "explicit_tests"          # a user test is official, whatever its id


# ---- heuristic tests ------------------------------------------------------------------------------


def test_heuristic_tests_are_capped_tagged_and_not_official():
    fns, _ = generate_tests(demo_spec())
    for name in ("to_kelvin", "is_safe", "landing_grade", "mission_clock", "average_speed"):
        heur = [g for g in by_function(fns, name) if g.category == "heuristic_tests"]
        assert 1 <= len(heur) <= MAX_HEURISTIC_PER_FUNCTION, name
        assert [g.test.id for g in heur] == [f"{name}#heur{n}" for n in range(1, len(heur) + 1)]
        for g in heur:
            assert g.test.origin.provenance == "heuristic"
            assert g.test.origin.confidence == HEURISTIC_CONFIDENCE
            assert "not from the subject" in (g.test.origin.note or "")
    landing = [g for g in by_function(fns, "landing_grade") if g.category == "heuristic_tests"]
    assert [(g.test.args, g.test.expected_return) for g in landing] == [
        (["0"], "'Perfect touchdown'"), (["-1"], "'Perfect touchdown'"), (["1000000"], "'Crash!'"),
    ]


def test_heuristic_without_oracle_is_a_type_only_check_and_errors_are_skipped():
    bare = make_fn("mystery", [("x", "int")], "int")
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("mystery", bare)]))
    assert [g.category for g in fns] == ["heuristic_tests"] * 3
    assert all(g.test.expected_return is None and g.test.expected_type == "int" for g in fns)

    inverse = make_fn("inverse", [("x", "int")], "float", reference="1 / x")
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("inverse", inverse)]))
    assert [(g.test.args, g.test.expected_return) for g in fns] == [(["-1"], "-1.0"), (["1000000"], "1e-06")]


def test_printing_functions_get_no_return_value_expectations():
    shout = make_fn("shout_grade", [("vertical_speed", "int")], None,
                    rules=[("vertical_speed <= 2", "'Perfect touchdown'"), (None, "'Crash!'")],
                    tests=[(["1"], None)])
    shout = shout.model_copy(update={"must_return": False, "may_print": True})
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("shout", shout)]))
    assert not [g for g in fns if g.category == "derived_tests"]
    assert all(g.test.expected_return is None for g in fns)
    assert next(g for g in fns if g.category == "explicit_tests").test.expected_return is None


def test_string_parameters_get_an_empty_string_case():
    greet = make_fn("greet", [("name", "str")], "str", reference="f'Hello {name}'", tests=[(["'Fred'"], "'Hello Fred'")])
    fns, _ = generate_tests(PracticalSpec(exercises=[exercise("greet", greet)]))
    heur = [g for g in fns if g.category == "heuristic_tests"]
    assert [(g.test.args, g.test.expected_return) for g in heur] == [(["''"], "'Hello '")]


# ---- script tests ---------------------------------------------------------------------------------


def test_script_tests_category_output_when_stdout_is_known():
    steps = [InteractionStep(kind="output", text="Enter access code: "), InteractionStep(kind="input", text="SCOOBY"),
             InteractionStep(kind="output", text="Access granted. Welcome aboard!\n")]
    script = ScriptSpec(prompts=["Enter access code: "], tests=[
        ScriptTest(id="access_code#session1", steps=steps),
        ScriptTest(id="access_code#session2", stdin="x\n", expected_stdout=None),
    ])
    spec = PracticalSpec(exercises=[exercise("access_code", kind="script", script=script)])
    fns, scripts = generate_tests(spec)
    assert fns == []
    assert [(s.test.id, s.category, s.exercise_id) for s in scripts] == [
        ("access_code#session1", "output", "access_code"), ("access_code#session2", "explicit_tests", "access_code"),
    ]
    assert scripts[0].test.stdin == "SCOOBY\n"
    assert scripts[0].test.expected_stdout == "Enter access code: Access granted. Welcome aboard!\n"
    assert scripts[0].test is not spec.exercises[0].script.tests[0]
