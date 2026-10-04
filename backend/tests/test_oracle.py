import ast
import time
from pathlib import Path

import pytest

from premoulinette.spec.models import BehaviorRule, FunctionSignature, FunctionSpec, FunctionTest, Param
from premoulinette.testgen import oracle
from premoulinette.testgen.oracle import (
    OracleError,
    boundary_cases,
    boundary_values,
    expected_for,
    expected_outcome,
    literal,
    parse_expr,
    safe_eval,
)


def make_fn(name, params, ret=None, rules=(), reference=None, tests=()):
    return FunctionSpec(
        signature=FunctionSignature(
            name=name, params=[Param(name=n, annotation=a) for n, a in params], return_annotation=ret
        ),
        rules=[BehaviorRule(when=w, returns=r) for w, r in rules],
        reference=reference,
        tests=[FunctionTest(id=f"{name}#ex{i + 1}", function=name, args=list(a), expected_return=e)
               for i, (a, e) in enumerate(tests)],
    )


IS_SAFE = make_fn(
    "is_safe", [("speed", "int"), ("limit", "int")], "bool",
    rules=[("speed <= limit", "True"), (None, "False")],
    tests=[(["200", "250"], "True"), (["300", "250"], "False")],
)
LANDING = make_fn(
    "landing_grade", [("vertical_speed", "int")], "str",
    rules=[("vertical_speed <= 2", "'Perfect touchdown'"), ("2 < vertical_speed <= 5", "'Hard landing'"),
           ("vertical_speed > 5", "'Crash!'")],
    tests=[(["1"], "'Perfect touchdown'"), (["4"], "'Hard landing'"), (["9"], "'Crash!'")],
)
AVERAGE = make_fn(
    "average_speed", [("distance", "float"), ("hours", "float")], "float",
    rules=[("hours == 0", "0.0"), (None, "distance / hours")],
    tests=[(["150.0", "2.0"], "75.0"), (["10.0", "0.0"], "0.0")],
)


# ---- safe subset ---------------------------------------------------------------------------------


@pytest.mark.parametrize("src", [
    "().__class__", "x.__class__", "__import__('os')", "open('f')", "eval('1')", "exec('1')",
    "compile('1', 'f', 'eval')", "getattr(x, 'y')", "lambda: 1", "[i for i in x]", "(y := 3)",
    "{**x}", "f(*x)", "x.upper()", "abs(x, key=1)", "sorted(x, key=len)", "...", "__builtins__",
    "x if", "",
])
def test_parse_expr_rejects_unsafe_or_invalid(src):
    with pytest.raises(OracleError):
        parse_expr(src)


def test_parse_expr_rejects_deep_and_long_inputs():
    with pytest.raises(OracleError):
        parse_expr("-" * 60 + "1")
    with pytest.raises(OracleError):
        parse_expr("(" * 500 + "1" + ")" * 500)
    with pytest.raises(OracleError):
        parse_expr("1 + " * 5000 + "1")


def test_arithmetic_and_comparisons():
    env = {"x": 4, "limit": 5, "s": "Mill"}
    assert safe_eval("x * 2 + 1", env) == 9
    assert safe_eval("x // 3, x % 3, -x, +x, ~x, x ** 2", env) == (1, 1, -4, 4, -5, 16)
    assert safe_eval("2 < x <= 5", env) is True
    assert safe_eval("2 < x <= 3", env) is False
    assert safe_eval("x <= limit < 3", env) is False
    assert safe_eval("x != 4 or s == 'Mill'", env) is True
    assert safe_eval("not x", env) is False
    assert safe_eval("'il' in s and 'z' not in s", env) is True
    assert safe_eval("x is None", {"x": None}) is True


def test_short_circuit_avoids_evaluating_the_right_side():
    assert safe_eval("x != 0 and 10 / x > 1", {"x": 0}) is False
    assert safe_eval("x == 0 or 10 / x > 1", {"x": 0}) is True
    assert safe_eval("0 if x == 0 else 10 / x", {"x": 0}) == 0


def test_containers_subscripts_and_safe_functions():
    env = {"xs": [3, 1, 2], "name": "Velma"}
    assert safe_eval("[xs[0], xs[-1], xs[1:], name[::-1]]", env) == [3, 2, [1, 2], "amleV"]
    assert safe_eval("{'a': len(xs)}['a']", env) == 3
    assert safe_eval("{1, 2} | {3}", env) == {1, 2, 3}
    assert safe_eval("abs(-3) + min(xs) + max(xs) + sum(xs)", env) == 3 + 1 + 3 + 6
    assert safe_eval("sorted(xs, reverse=True)", env) == [3, 2, 1]
    assert safe_eval("round(2.675, ndigits=1), int('7'), float('1.5'), str(12), bool(0)", env) == (2.7, 7, 1.5, "12", False)


def test_fstrings_with_conversion_and_format_spec():
    env = {"seconds": 3725, "name": "Fred", "w": 6, "x": 3.14159}
    ref = 'f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"'
    assert safe_eval(ref, env) == "01:02:05"
    assert safe_eval(ref, {"seconds": 0}) == "00:00:00"
    assert safe_eval("f'{name!r} {name!s} {name!a}'", env) == "'Fred' Fred 'Fred'"
    assert safe_eval("f'{x:.2f}|{name:>{w}}|{name=}'", env) == "3.14|  Fred|name='Fred'"
    assert safe_eval("'%05.1f' % x", env) == "003.1"


def test_division_by_zero_and_runtime_errors_raise_oracle_error():
    with pytest.raises(OracleError, match="division by zero"):
        safe_eval("distance / hours", {"distance": 1.0, "hours": 0.0})
    with pytest.raises(OracleError):
        safe_eval("x % 0", {"x": 3})
    with pytest.raises(OracleError, match="unknown name"):
        safe_eval("y + 1", {"x": 1})
    with pytest.raises(OracleError):
        safe_eval("'a' + 1", {})
    with pytest.raises(OracleError):
        safe_eval("xs[10]", {"xs": [1]})


@pytest.mark.parametrize("src", [
    "2 ** 1001", "9 ** 9 ** 9", "(10 ** 1000) ** 1000", "'a' * 10001", "[0] * 10 ** 6", "1 << 10 ** 6",
    "f'{1:99999999}'", "f'{1:.{n}f}'", "'%999999d' % 1", "round(5, -10 ** 9)", "sum([[1] * 5000] * 2, [])",
    "[[1] * 5000] * 5000", "str(10 ** 6000)",
])
def test_resource_guards(src):
    started = time.perf_counter()
    with pytest.raises(OracleError):
        safe_eval(src, {"n": 10 ** 7})
    assert time.perf_counter() - started < 2


def test_literal_wrapper():
    assert literal("'True'") == "True"
    assert literal(" (1, 2.5, None) ") == (1, 2.5, None)
    assert literal("-3") == -3
    for bad in ("x", "f(1)", "1 +", "__import__('os')"):
        with pytest.raises(OracleError):
            literal(bad)


def test_oracle_module_never_calls_eval_exec_or_compile():
    tree = ast.parse(Path(oracle.__file__).read_text(encoding="utf-8"))
    calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = {f.id for f in calls if isinstance(f, ast.Name)}
    attrs = {f.attr for f in calls if isinstance(f, ast.Attribute)}   # re.compile is a regex, allowed
    assert not names & {"eval", "exec", "compile", "__import__"}
    assert not attrs & {"eval", "exec"}


# ---- expected values -------------------------------------------------------------------------------


def test_expected_for_rules_first_match_and_otherwise():
    assert expected_for(IS_SAFE, [200, 250]) == (True, True, "speed <= limit → True")
    assert expected_for(IS_SAFE, [251, 250]) == (True, False, "otherwise → False")
    assert expected_for(LANDING, [2]) == (True, "Perfect touchdown", "vertical_speed <= 2 → 'Perfect touchdown'")
    assert expected_for(LANDING, [3])[1] == "Hard landing"
    assert expected_for(LANDING, [6])[1] == "Crash!"


def test_expected_for_reference_and_guarded_rule():
    kelvin = make_fn("to_kelvin", [("celsius", "float")], "float", reference="celsius + 273.15")
    known, value, rule = expected_for(kelvin, [0])
    assert known and value == pytest.approx(273.15) and rule == "returns celsius + 273.15"
    assert expected_for(AVERAGE, [10.0, 0.0])[1] == 0.0
    assert expected_for(AVERAGE, [150.0, 2.0])[1] == 75.0


def test_expected_for_unknown_and_errors():
    bare = make_fn("f", [("x", "int")], "int")
    assert expected_for(bare, [1]) == (False, None, None)
    partial = make_fn("g", [("x", "int")], "int", rules=[("x > 0", "1")])
    assert expected_outcome(partial, [-1]).kind == "unknown"
    inv = make_fn("inv", [("x", "int")], "float", reference="1 / x")
    outcome = expected_outcome(inv, [0])
    assert outcome.kind == "error" and "division by zero" in (outcome.reason or "")
    assert expected_outcome(IS_SAFE, [1]).kind == "error"          # missing argument


def test_expected_outcome_raises_rule_and_defaults():
    fn = FunctionSpec(
        signature=FunctionSignature(name="h", params=[Param(name="x", annotation="int"), Param(name="k", default="2")]),
        rules=[BehaviorRule(when="x < 0", raises="ValueError"), BehaviorRule(returns="x * k")],
    )
    raised = expected_outcome(fn, [-1])
    assert raised.kind == "raises" and raised.exception == "ValueError" and raised.rule_text == "x < 0 → raises ValueError"
    assert expected_outcome(fn, [3]).value == 6
    assert expected_outcome(fn, [3], {"k": 10}).value == 30


# ---- boundary values ---------------------------------------------------------------------------


def test_boundary_values_param_vs_param_uses_explicit_base():
    assert boundary_values(IS_SAFE) == [
        {"speed": 250, "limit": 250}, {"speed": 251, "limit": 250}, {"speed": 249, "limit": 250},
    ]
    descriptions = [c.description for c in boundary_cases(IS_SAFE)]
    assert descriptions == ["speed == limit", "speed == limit + 1", "speed == limit - 1"]


def test_boundary_values_chained_comparisons_are_deduplicated():
    values = [a["vertical_speed"] for a in boundary_values(LANDING)]
    assert values == [1, 2, 3, 4, 5, 6]


def test_boundary_values_float_annotation_and_other_params_from_first_test():
    assert boundary_values(AVERAGE) == [
        {"distance": 150.0, "hours": 0.0}, {"distance": 150.0, "hours": 0.5}, {"distance": 150.0, "hours": -0.5},
    ]


def test_boundary_values_constant_on_left_negative_constants_and_strings():
    fn = make_fn("f", [("x", "int"), ("name", "str")], "int",
                 rules=[("0 < x and name == 'admin'", "1"), ("x >= -5", "2")])
    assignments = boundary_values(fn)
    assert {"x": -1, "name": "a"} in assignments and {"x": 1, "name": "a"} in assignments
    assert {"x": 1, "name": "admin"} in assignments
    assert {"x": -6, "name": "a"} in assignments and {"x": -4, "name": "a"} in assignments


def test_boundary_values_type_defaults_without_tests():
    fn = make_fn("f", [("a", "int"), ("b", "float"), ("c", "str"), ("d", "bool")], "int", rules=[("a > 10", "1")])
    assert boundary_values(fn) == [
        {"a": 9, "b": 1.0, "c": "a", "d": True}, {"a": 10, "b": 1.0, "c": "a", "d": True},
        {"a": 11, "b": 1.0, "c": "a", "d": True},
    ]


def test_boundary_values_int_param_with_float_constant_and_unparsable_rules():
    fn = make_fn("f", [("x", "int")], "int", rules=[("x <= 2.5", "1"), ("x.y > 3", "2"), ("len(s) > 3", "3")])
    assert [a["x"] for a in boundary_values(fn)] == [2, 3]


def test_boundary_values_ignore_unknown_typed_params():
    fn = make_fn("f", [("xs", "list[int]")], "int", rules=[("xs == 3", "1")])
    assert boundary_values(fn) == []
