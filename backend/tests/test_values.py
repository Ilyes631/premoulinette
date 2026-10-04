import pytest

from premoulinette.compare.values import annotation_types, compare_values, match_values, runtime_failure
from premoulinette.results.models import ValueSnapshot
from premoulinette.runner.models import JobResult, RawException


def ok(value_repr, type_name, *, literal=True, stdout=""):
    return JobResult(id="t", kind="function", status="ok", return_repr=value_repr, return_type=type_name,
                     return_literal=literal, stdout=stdout)


def failed(status, *, exc_type=None, message="", line=None, blocked=()):
    exception = RawException(type=exc_type, message=message, file="pkg/mod.py", line=line) if exc_type else None
    return JobResult(id="t", kind="function", status=status, exception=exception, blocked_syscalls=list(blocked))


# ---- product brief ---------------------------------------------------------------------------------


def test_is_safe_returning_the_string_true():
    verdict = compare_values("True", "bool", ok("'True'", "str"), compare="auto", annotation="bool")
    assert not verdict.ok and verdict.status == "fail"
    assert verdict.kind == "str_instead_of_bool" and verdict.diagnosis == "str_instead_of_bool"
    assert verdict.severity == "major"
    assert verdict.expected == ValueSnapshot(repr="True", type="bool")
    assert verdict.actual == ValueSnapshot(repr="'True'", type="str")
    assert verdict.message == 'Returned the string "True" (str) instead of the boolean True (bool).'


def test_string_false_for_false():
    verdict = compare_values("False", None, ok("'False'", "str"), compare="auto", annotation=None)
    assert verdict.diagnosis == "str_instead_of_bool"
    assert 'instead of the boolean False (bool)' in verdict.message


# ---- equality and strict typing ----------------------------------------------------------------------


def test_equal_values_pass():
    for expected, actual, type_name in [("True", "True", "bool"), ("'Crash!'", "'Crash!'", "str"), ("133", "133", "int"),
                                         ("(1, 'a')", "(1, 'a')", "tuple"), ("None", "None", "NoneType")]:
        verdict = compare_values(expected, None, ok(actual, type_name), compare="auto", annotation=None)
        assert verdict.ok and verdict.status == "pass" and verdict.kind == "equal", (expected, verdict)
        assert verdict.diagnosis is None and verdict.severity is None


def test_double_quoted_expected_literal_equals_single_quoted_repr():
    verdict = compare_values('"Hard landing"', None, ok("'Hard landing'", "str"), compare="auto", annotation=None)
    assert verdict.ok and verdict.expected == ValueSnapshot(repr="'Hard landing'", type="str")


def test_bool_is_not_int():
    verdict = compare_values("1", None, ok("True", "bool"), compare="auto", annotation=None)
    assert not verdict.ok and verdict.diagnosis == "wrong_type"
    verdict = compare_values("True", None, ok("1", "int"), compare="auto", annotation=None)
    assert not verdict.ok and verdict.diagnosis == "wrong_type"
    assert verdict.message == "Returned 1 (int) instead of True (bool)."


def test_float_tolerance_in_auto_mode():
    verdict = compare_values("0.3", None, ok("0.30000000000000004", "float"), compare="auto", annotation=None)
    assert verdict.ok and verdict.kind == "float_close" and verdict.status == "pass"
    verdict = compare_values("273.15", None, ok("273.15", "float"), compare="auto", annotation=None)
    assert verdict.kind == "equal"
    far = compare_values("75.0", None, ok("75.5", "float"), compare="auto", annotation=None)
    assert not far.ok and far.diagnosis == "wrong_value" and far.severity == "major"


def test_exact_mode_disables_tolerance_and_int_for_float():
    verdict = compare_values("0.3", None, ok("0.30000000000000004", "float"), compare="exact", annotation=None)
    assert not verdict.ok and verdict.diagnosis == "wrong_value"
    verdict = compare_values("75.0", None, ok("75", "int"), compare="exact", annotation=None)
    assert not verdict.ok and verdict.diagnosis == "wrong_type"


def test_int_instead_of_float_is_a_warning():
    verdict = compare_values("0.0", "float", ok("0", "int"), compare="auto", annotation="float")
    assert verdict.ok and verdict.status == "warning" and verdict.kind == "int_instead_of_float"
    assert verdict.diagnosis == "int_instead_of_float" and verdict.severity == "minor"


def test_float_instead_of_int_is_a_wrong_type():
    verdict = compare_values("133", None, ok("133.0", "float"), compare="auto", annotation="int")
    assert not verdict.ok and verdict.diagnosis == "wrong_type"
    assert verdict.message == "Returned 133.0 (float) instead of 133 (int)."
    verdict = compare_values("133", None, ok("133.33333333333334", "float"), compare="auto", annotation="int")
    assert verdict.diagnosis == "wrong_type"


def test_number_returned_as_string():
    verdict = compare_values("273.15", None, ok("'273.15'", "str"), compare="auto", annotation=None)
    assert verdict.diagnosis == "number_as_str" and verdict.severity == "major"
    assert verdict.message == 'Returned the string "273.15" (str) instead of the number 273.15 (float).'


def test_containers_compare_recursively_with_tolerance():
    assert compare_values("[1, 2.0]", None, ok("[1, 2.0000000000001]", "list"), compare="auto", annotation=None).kind == "float_close"
    assert compare_values("(1, 2)", None, ok("[1, 2]", "list"), compare="auto", annotation=None).diagnosis == "wrong_type"
    assert compare_values("{'a': 1}", None, ok("{'a': 2}", "dict"), compare="auto", annotation=None).diagnosis == "wrong_value"
    assert match_values([1.0, 2.0], [1, 2.0], tolerant=True) == "int_for_float"
    assert match_values({1, 2}, {2, 1}, tolerant=False) == "equal"
    assert match_values({True}, {1}, tolerant=False) == "different"


# ---- None / printing ---------------------------------------------------------------------------------


def test_returns_none():
    verdict = compare_values("'Hard landing'", None, ok("None", "NoneType"), compare="auto", annotation="str")
    assert verdict.diagnosis == "returns_none" and verdict.severity == "major"
    assert verdict.actual == ValueSnapshot(repr="None", type="NoneType")


def test_prints_instead_of_returns_when_stdout_shows_the_value():
    res = ok("None", "NoneType", stdout="Hard landing\n")
    verdict = compare_values("'Hard landing'", None, res, compare="auto", annotation="str")
    assert verdict.diagnosis == "prints_instead_of_returns"
    assert "printed 'Hard landing'" in verdict.message
    res = ok("None", "NoneType", stdout="'01:02:05'\n")
    assert compare_values("'01:02:05'", None, res, compare="auto", annotation=None).diagnosis == "prints_instead_of_returns"
    res = ok("None", "NoneType", stdout="True\n")
    assert compare_values("True", None, res, compare="auto", annotation=None).diagnosis == "prints_instead_of_returns"


def test_short_values_need_a_whole_printed_line():
    res = ok("None", "NoneType", stdout="debug 1 2 3\n")
    assert compare_values("1", None, res, compare="auto", annotation=None).diagnosis == "returns_none"
    res = ok("None", "NoneType", stdout="1\n")
    assert compare_values("1", None, res, compare="auto", annotation=None).diagnosis == "prints_instead_of_returns"


# ---- strings -------------------------------------------------------------------------------------------


def test_wrong_string_with_typo_is_minor_and_has_a_diff():
    verdict = compare_values("'Hard landing'", None, ok("'Hard Landing'", "str"), compare="auto", annotation=None)
    assert verdict.diagnosis == "wrong_string" and verdict.severity == "minor" and verdict.status == "fail"
    assert verdict.value_diff is not None and not verdict.value_diff.equal
    assert verdict.value_diff.expected == "Hard landing" and verdict.value_diff.actual == "Hard Landing"
    assert "case differs: 'l' → 'L' (col 6)" in verdict.message


def test_wrong_string_trailing_space_and_completely_different():
    verdict = compare_values("'Crash!'", None, ok("'Crash! '", "str"), compare="auto", annotation=None)
    assert verdict.severity == "minor" and "extra trailing space" in verdict.message
    verdict = compare_values("'Crash!'", None, ok("'Perfect touchdown'", "str"), compare="auto", annotation=None)
    assert verdict.diagnosis == "wrong_string" and verdict.severity == "major"


# ---- runtime failures -----------------------------------------------------------------------------------


def test_exception_verdict_is_critical_with_location():
    verdict = compare_values("1", None, failed("exception", exc_type="ZeroDivisionError", message="division by zero",
                                                line=4), compare="auto", annotation=None)
    assert verdict.diagnosis == "exception" and verdict.severity == "critical" and not verdict.ok
    assert verdict.message == "The call raised ZeroDivisionError: division by zero (line 4 of pkg/mod.py)."


def test_eof_in_a_function_call_explains_input():
    verdict = compare_values("1", None, failed("exception", exc_type="EOFError", message="EOF when reading a line"),
                             compare="auto", annotation=None)
    assert "must not read input" in verdict.message


@pytest.mark.parametrize(("status", "diagnosis"), [
    ("timeout", "timeout"), ("output_limit", "output_limit"), ("import_error", "import_crash"),
    ("syntax_error", "syntax_error"), ("crash", "exception"),
])
def test_runtime_statuses(status, diagnosis):
    verdict = compare_values("1", None, failed(status), compare="auto", annotation=None)
    assert not verdict.ok and verdict.diagnosis == diagnosis and verdict.severity == "critical"


def test_blocked_syscall_wins():
    res = failed("exception", exc_type="PermissionError", message="blocked", blocked=["socket.connect", "socket.connect"])
    verdict = compare_values("1", None, res, compare="auto", annotation=None)
    assert verdict.diagnosis == "blocked_syscall" and "socket.connect" in verdict.message
    assert verdict.message.count("socket.connect") == 1


def test_runtime_failure_is_none_for_ok_jobs():
    assert runtime_failure(ok("1", "int"), context="call") is None
    script = runtime_failure(failed("timeout"), context="script")
    assert script is not None and script.message.startswith("The program")


# ---- type-only checks ------------------------------------------------------------------------------------


def test_type_only_checks_against_annotation():
    assert compare_values(None, None, ok("3", "int"), compare="auto", annotation="int").kind == "type_ok"
    warn = compare_values(None, None, ok("3", "int"), compare="auto", annotation="float")
    assert warn.ok and warn.status == "warning" and warn.diagnosis == "int_instead_of_float"
    wrong = compare_values(None, None, ok("'3'", "str"), compare="auto", annotation="int")
    assert wrong.diagnosis == "number_as_str"
    wrong = compare_values(None, "bool", ok("'True'", "str"), compare="auto", annotation="int")
    assert wrong.diagnosis == "str_instead_of_bool"           # expected_type wins over the annotation
    assert compare_values(None, None, ok("None", "NoneType"), compare="auto", annotation="int | None").ok
    assert compare_values(None, None, ok("None", "NoneType"), compare="auto", annotation="Optional[int]").ok
    none = compare_values(None, None, ok("None", "NoneType", stdout="42\n"), compare="auto", annotation="int")
    assert none.diagnosis == "prints_instead_of_returns"
    assert compare_values(None, None, ok("None", "NoneType"), compare="auto", annotation="str").diagnosis == "returns_none"
    assert compare_values(None, None, ok("[1]", "list"), compare="auto", annotation="list[int]").kind == "type_ok"
    assert compare_values(None, None, ok("1.5", "float"), compare="auto", annotation="int").diagnosis == "wrong_type"


def test_type_only_without_or_with_unknown_annotation_only_checks_no_crash():
    assert compare_values(None, None, ok("3", "int"), compare="auto", annotation=None).kind == "no_crash"
    verdict = compare_values(None, None, ok("<Foo>", "Foo", literal=False), compare="auto", annotation="Foo")
    assert verdict.ok and verdict.kind == "type_unchecked"


def test_annotation_types():
    assert annotation_types("int | None") == {"int", "NoneType"}
    assert annotation_types("typing.Optional[str]") == {"str", "NoneType"}
    assert annotation_types("Union[int, float]") == {"int", "float"}
    assert annotation_types("dict[str, list[int]]") == {"dict"}
    assert annotation_types("'bool'") == {"bool"}
    assert annotation_types("MyClass") is None


# ---- non-literal values ----------------------------------------------------------------------------------


def test_non_literal_expected_compares_representations():
    res = ok("Point(x=1, y=2)", "Point", literal=False)
    assert compare_values("Point(x=1, y=2)", "Point", res, compare="auto", annotation=None).ok
    verdict = compare_values("Point(x=1, y=3)", "Point", res, compare="auto", annotation=None)
    assert verdict.diagnosis == "wrong_value"


def test_non_literal_actual_against_literal_expected():
    res = ok("<object object at 0x1>", "object", literal=False)
    verdict = compare_values("1", None, res, compare="auto", annotation=None)
    assert verdict.diagnosis == "wrong_type"
