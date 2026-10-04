"""Compare the value returned by a function call (JobResult) with the expected literal.

Strict typing: ``True`` (bool) is not ``1`` (int) nor ``'True'`` (str). Floats are compared with a
tight tolerance (``math.isclose(rel_tol=1e-9, abs_tol=1e-9)``) unless ``compare == "exact"``.
An ``int`` where a ``float`` is expected is accepted with a warning (numeric tower), the reverse is
a wrong type.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from premoulinette.compare.text_diff import diff_text, first_hint, only_minor
from premoulinette.results.models import Severity, TextDiff, ValueSnapshot
from premoulinette.runner.models import JobResult
from premoulinette.spec.models import CompareMode
from premoulinette.testgen.oracle import OracleError, literal

REL_TOL = 1e-9
ABS_TOL = 1e-9
MAX_SHOWN = 120

VerdictStatus = Literal["pass", "warning", "fail"]


class ValueVerdict(BaseModel):
    ok: bool                          # pass or warning
    kind: str
    severity: Severity | None = None
    title: str
    message: str
    diagnosis: str | None = None
    status: VerdictStatus = "pass"
    expected: ValueSnapshot | None = None
    actual: ValueSnapshot | None = None
    value_diff: TextDiff | None = None


def compare_values(
    expected_src: str | None,
    expected_type: str | None,
    res: JobResult,
    *,
    compare: CompareMode = "auto",
    annotation: str | None = None,
) -> ValueVerdict:
    failure = runtime_failure(res, context="call")
    if failure is not None:
        return failure
    actual = _Actual.from_result(res)
    if expected_src is None:
        return _check_type_only(expected_type or annotation, actual, res)
    try:
        expected = literal(expected_src)
    except OracleError:
        return _compare_repr(expected_src.strip(), expected_type, actual)
    return _compare_known(expected, actual, res, compare)


# ------------------------------------------------------------------------------------------------
# Runtime failures (exception, timeout...)
# ------------------------------------------------------------------------------------------------


def _fail(kind: str, severity: Severity, title: str, message: str, diagnosis: str | None, **extra: object) -> ValueVerdict:
    return ValueVerdict(ok=False, kind=kind, severity=severity, title=title, message=message,
                        diagnosis=diagnosis, status="fail", **extra)  # type: ignore[arg-type]


def _where(res: JobResult) -> str:
    exc = res.exception
    if exc is None or exc.line is None:
        return ""
    return f" (line {exc.line} of {exc.file})" if exc.file else f" (line {exc.line})"


def runtime_failure(res: JobResult, *, context: Literal["call", "script", "import"]) -> ValueVerdict | None:
    """Verdict for a job that did not complete normally, else None."""
    subject = {"call": "The call", "script": "The program", "import": "Importing the module"}[context]
    if res.blocked_syscalls:
        ops = ", ".join(dict.fromkeys(res.blocked_syscalls))
        return _fail("blocked_syscall", "critical", "Forbidden operation blocked",
                     f"{subject} tried a forbidden operation ({ops}); the sandbox blocked it.", "blocked_syscall")
    exc = res.exception
    exc_text = f"{exc.type}: {exc.message}" if exc else "unknown error"
    if res.status == "timeout":
        return _fail("timeout", "critical", "Time limit exceeded",
                     f"{subject} did not finish within the time limit (infinite loop?).", "timeout")
    if res.status == "output_limit":
        return _fail("output_limit", "critical", "Too much output",
                     f"{subject} printed more than the output limit (infinite print loop?).", "output_limit")
    if res.status == "import_error":
        return _fail("import_error", "critical", "Module import failed",
                     f"Importing the module failed: {exc_text}{_where(res)}.", "import_crash")
    if res.status == "syntax_error":
        return _fail("syntax_error", "critical", "Syntax error",
                     f"The module could not be compiled: {exc_text}{_where(res)}.", "syntax_error")
    if res.status == "crash":
        return _fail("crash", "critical", "Process crashed",
                     f"{subject} crashed the test process ({exc_text}).", "exception")
    if res.status == "harness_error":
        return _fail("harness_error", "critical", "Test harness error",
                     f"The test could not be run by the harness: {res.harness_error or exc_text}.", None)
    if res.status == "exception":
        hint = ""
        if exc is not None and exc.type == "EOFError" and context == "call":
            hint = " The function called input(): functions must not read input."
        return _fail("exception", "critical", f"Raised {exc.type if exc else 'an exception'}",
                     f"{subject} raised {exc_text}{_where(res)}.{hint}", "exception")
    return None


# ------------------------------------------------------------------------------------------------
# Value comparison
# ------------------------------------------------------------------------------------------------

_NO_VALUE = object()


@dataclass(frozen=True)
class _Actual:
    repr: str
    type: str
    value: object          # _NO_VALUE when the repr is not a literal

    @classmethod
    def from_result(cls, res: JobResult) -> _Actual:
        rtype = res.return_type or "NoneType"
        rrepr = res.return_repr if res.return_repr is not None else "None"
        value: object = _NO_VALUE
        if rrepr == "None" and rtype == "NoneType":
            value = None
        elif res.return_literal:
            try:
                value = literal(rrepr)
            except OracleError:
                value = _NO_VALUE
        return cls(rrepr, rtype, value)

    @property
    def snapshot(self) -> ValueSnapshot:
        return ValueSnapshot(repr=self.repr, type=self.type)


def type_name(value: object) -> str:
    return type(value).__name__


def _short(text: str) -> str:
    return text if len(text) <= MAX_SHOWN else text[: MAX_SHOWN - 1] + "…"


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _has_float(v: object) -> bool:
    if isinstance(v, float):
        return True
    if isinstance(v, (list, tuple, set, frozenset)):
        return any(_has_float(x) for x in v)
    if isinstance(v, dict):
        return any(_has_float(x) for x in v.values())
    return False


_MATCH_RANK = {"equal": 0, "close": 1, "int_for_float": 2, "different": 3}


def _worst(results: list[str]) -> str:
    return max(results, key=_MATCH_RANK.__getitem__, default="equal")


def match_values(expected: object, actual: object, tolerant: bool) -> str:
    """'equal' | 'close' (float tolerance) | 'int_for_float' | 'different' — strict on types."""
    if _is_number(expected) and _is_number(actual):
        if type(expected) is type(actual):
            if expected == actual:
                return "equal"
            if tolerant and isinstance(expected, float) and math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL):  # type: ignore[arg-type]
                return "close"
            return "different"
        if isinstance(expected, float) and isinstance(actual, int):
            close = expected == actual or (tolerant and math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL))
            return "int_for_float" if close else "different"
        return "different"
    if type(expected) is not type(actual):
        return "different"
    if isinstance(expected, (list, tuple)):
        assert isinstance(actual, (list, tuple))
        if len(expected) != len(actual):
            return "different"
        return _worst([match_values(e, a, tolerant) for e, a in zip(expected, actual)])
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        if expected.keys() != actual.keys():
            return "different"
        return _worst([match_values(expected[k], actual[k], tolerant) for k in expected])
    if isinstance(expected, (set, frozenset)):
        same = expected == actual and sorted(map(repr, expected)) == sorted(map(repr, actual))  # type: ignore[arg-type]
        return "equal" if same else "different"
    return "equal" if expected == actual else "different"


def _numeric_string(s: str) -> bool:
    try:
        float(s.strip())
    except ValueError:
        return False
    return bool(s.strip())


def _printed_value(expected: object, stdout: str) -> str | None:
    """The stdout line showing ``expected`` (the function printed instead of returning), if any."""
    if not stdout:
        return None
    candidates = {str(expected), repr(expected)}
    for line in stdout.splitlines():
        if line.strip() in candidates:
            return line
    shown = str(expected)
    if len(shown) >= 3 and shown in stdout:
        return shown
    return None


def _compare_known(expected: object, actual: _Actual, res: JobResult, compare: CompareMode) -> ValueVerdict:
    exp_snap = ValueSnapshot(repr=repr(expected), type=type_name(expected))
    act_snap = actual.snapshot
    snaps = {"expected": exp_snap, "actual": act_snap}
    e_r, a_r = _short(exp_snap.repr), _short(act_snap.repr)

    if actual.value is _NO_VALUE:     # non-literal object (instance, function...)
        if actual.repr == exp_snap.repr and actual.type == exp_snap.type:
            return ValueVerdict(ok=True, kind="equal", title="Correct return value",
                                message=f"Returned {a_r} as expected.", **snaps)
        if actual.type != exp_snap.type:
            return _wrong_type(e_r, exp_snap.type, a_r, act_snap.type, snaps)
        return _fail("wrong_value", "major", "Wrong return value", f"Returned {a_r} instead of {e_r}.", "wrong_value", **snaps)

    value = actual.value
    tolerant = compare == "float_tolerance" or (compare == "auto" and (_has_float(expected) or _has_float(value)))
    match = match_values(expected, value, tolerant)
    if match == "equal":
        return ValueVerdict(ok=True, kind="equal", title="Correct return value", message=f"Returned {a_r} as expected.", **snaps)
    if match == "close":
        return ValueVerdict(ok=True, kind="float_close", title="Correct return value (float tolerance)",
                            message=f"Returned {a_r}, equal to {e_r} within floating-point tolerance.", **snaps)
    if match == "int_for_float":
        if compare == "exact":
            return _wrong_type(e_r, exp_snap.type, a_r, act_snap.type, snaps)
        return ValueVerdict(
            ok=True, kind="int_instead_of_float", severity="minor", status="warning", diagnosis="int_instead_of_float",
            title="Returns an int instead of a float",
            message=f"Returned {a_r} (int) instead of {e_r} (float): the value is right but the type differs.", **snaps,
        )
    if isinstance(expected, bool) and isinstance(value, str) and value.strip() in ("True", "False", "true", "false"):
        return _fail("str_instead_of_bool", "major", "Returns a string instead of a boolean",
                     f'Returned the string "{value}" (str) instead of the boolean {expected} (bool).',
                     "str_instead_of_bool", **snaps)
    if _is_number(expected) and isinstance(value, str) and _numeric_string(value):
        return _fail("number_as_str", "major", "Returns a string instead of a number",
                     f'Returned the string "{_short(value)}" (str) instead of the number {e_r} ({exp_snap.type}).',
                     "number_as_str", **snaps)
    if value is None and expected is not None:
        printed = _printed_value(expected, res.stdout)
        if printed is not None:
            return _fail("prints_instead_of_returns", "major", "Prints the result instead of returning it",
                         f"Returned None but printed {_short(printed)!r}: the function must return {e_r}, not print it.",
                         "prints_instead_of_returns", **snaps)
        return _fail("returns_none", "major", "Returns None",
                     f"Returned None instead of {e_r} ({exp_snap.type}): a return statement is missing for this case.",
                     "returns_none", **snaps)
    if isinstance(expected, str) and isinstance(value, str):
        diff = diff_text(expected, value)
        minor = only_minor(list(diff.kinds))
        severity: Severity = "minor" if minor else "major"
        # Character hints only help when the strings are near-identical (typo, case, spaces...);
        # for unrelated strings ("Hard landing" vs "Perfect touchdown") line-diff wording is noise.
        detail = f" ({first_hint(diff)})" if minor else ""
        return _fail("wrong_string", severity, "Wrong string",
                     f"Returned {a_r} instead of {e_r}{detail}.", "wrong_string", value_diff=diff, **snaps)
    numeric_pair = _is_number(expected) and _is_number(value)
    if type(expected) is not type(value) and not (numeric_pair and isinstance(expected, float)):
        return _wrong_type(e_r, exp_snap.type, a_r, act_snap.type, snaps)
    return _fail("wrong_value", "major", "Wrong return value", f"Returned {a_r} instead of {e_r}.", "wrong_value", **snaps)


def _wrong_type(e_r: str, e_t: str, a_r: str, a_t: str, snaps: dict[str, ValueSnapshot]) -> ValueVerdict:
    return _fail("wrong_type", "major", "Wrong return type", f"Returned {a_r} ({a_t}) instead of {e_r} ({e_t}).",
                 "wrong_type", **snaps)


def _compare_repr(expected_src: str, expected_type: str | None, actual: _Actual) -> ValueVerdict:
    """Expected value is not a literal (e.g. an object repr): compare representations."""
    snaps = {"expected": ValueSnapshot(repr=expected_src, type=expected_type or "unknown"), "actual": actual.snapshot}
    if actual.repr == expected_src:
        return ValueVerdict(ok=True, kind="equal", title="Correct return value",
                            message=f"Returned {_short(actual.repr)} as expected.", **snaps)
    return _fail("wrong_value", "major", "Wrong return value",
                 f"Returned {_short(actual.repr)} instead of {_short(expected_src)}.", "wrong_value", **snaps)


# ------------------------------------------------------------------------------------------------
# Type-only checks (no expected value, e.g. heuristic tests)
# ------------------------------------------------------------------------------------------------

_KNOWN_TYPES = {"int", "float", "str", "bool", "list", "tuple", "dict", "set", "frozenset", "NoneType", "bytes", "complex"}
_TYPE_ALIASES = {"List": "list", "Tuple": "tuple", "Dict": "dict", "Set": "set", "FrozenSet": "frozenset",
                 "None": "NoneType", "type(None)": "NoneType"}


def _split_top_level(text: str, sep: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for ch in text:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [p.strip() for p in parts if p.strip()]


def annotation_types(annotation: str) -> set[str] | None:
    """Accepted ``type(x).__name__`` values for a simple annotation; None if it cannot be checked."""
    text = annotation.strip().strip("'\"").strip()
    names: set[str] = set()
    for part in _split_top_level(text, "|"):
        part = re.sub(r"^typing\.", "", part)
        match = re.fullmatch(r"(Optional|Union)\[(.*)\]", part, flags=re.S)
        if match:
            inner = annotation_types(" | ".join(_split_top_level(match.group(2), ",")))
            if inner is None:
                return None
            names |= inner | ({"NoneType"} if match.group(1) == "Optional" else set())
            continue
        base = part.split("[", 1)[0].strip()
        base = _TYPE_ALIASES.get(base, base)
        if base not in _KNOWN_TYPES:
            return None
        names.add(base)
    return names or None


def _check_type_only(annotation: str | None, actual: _Actual, res: JobResult) -> ValueVerdict:
    snaps = {"actual": actual.snapshot}
    shown = _short(actual.repr)
    if not annotation:
        return ValueVerdict(ok=True, kind="no_crash", title="Completed without error",
                            message=f"The call returned {shown} without error.", **snaps)
    allowed = annotation_types(annotation)
    if allowed is None:
        return ValueVerdict(ok=True, kind="type_unchecked", title="Completed without error",
                            message=f"The call returned {shown} ({actual.type}); the type {annotation} was not checked.", **snaps)
    snaps["expected"] = ValueSnapshot(repr="?", type=annotation.strip())
    if actual.type in allowed:
        return ValueVerdict(ok=True, kind="type_ok", title="Correct return type",
                            message=f"The call returned {shown} ({actual.type}), as annotated.", **snaps)
    if actual.type == "int" and "float" in allowed:
        return ValueVerdict(ok=True, kind="int_instead_of_float", severity="minor", status="warning",
                            diagnosis="int_instead_of_float", title="Returns an int instead of a float",
                            message=f"Returned {shown} (int) where a float is expected.", **snaps)
    value = actual.value
    if "bool" in allowed and isinstance(value, str) and value.strip() in ("True", "False", "true", "false"):
        return _fail("str_instead_of_bool", "major", "Returns a string instead of a boolean",
                     f'Returned the string "{value}" (str) instead of a boolean (bool).', "str_instead_of_bool", **snaps)
    if allowed & {"int", "float"} and isinstance(value, str) and _numeric_string(value):
        return _fail("number_as_str", "major", "Returns a string instead of a number",
                     f'Returned the string "{_short(value)}" (str) instead of a number ({annotation}).', "number_as_str", **snaps)
    if actual.type == "NoneType":
        if res.stdout.strip():
            return _fail("prints_instead_of_returns", "major", "Prints the result instead of returning it",
                         f"Returned None but printed {_short(res.stdout.strip())!r}: the function must return its result.",
                         "prints_instead_of_returns", **snaps)
        return _fail("returns_none", "major", "Returns None",
                     f"Returned None instead of a value of type {annotation}.", "returns_none", **snaps)
    return _fail("wrong_type", "major", "Wrong return type",
                 f"Returned {shown} ({actual.type}) but the expected type is {annotation}.", "wrong_type", **snaps)
