"""Read-only accessors over ``CheckResult``/``Evidence``.

Producers (structure, static, eval agents) do not all fill evidence the same way, so these helpers try
the documented fields first, then a few well-known ``details`` keys, then the stable check id.
"""
from __future__ import annotations

import ast
import difflib
import re
from typing import Any

from premoulinette.results.models import CheckResult, DiffLine, Evidence, TextDiff, ValueSnapshot

_PATH_ID_PREFIXES = (
    "structure:file:",
    "structure:parasite:",
    "structure:extra:",
    "git:untracked:",
    "git:ignored:",
    "syntax:",
)
_IDENT_IN_QUOTES = re.compile(r"[`'\"]([A-Za-z_][A-Za-z0-9_]*)[`'\"]")


def evidence(check: CheckResult) -> Evidence:
    return check.evidence or Evidence()


def detail(check: CheckResult, *keys: str) -> Any:
    """First non-empty ``evidence.details[key]`` among ``keys``."""
    details = check.evidence.details if check.evidence else {}
    for key in keys:
        value = details.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def detail_str(check: CheckResult, *keys: str) -> str | None:
    value = detail(check, *keys)
    return value if isinstance(value, str) else None


def id_suffix(check: CheckResult, prefix: str) -> str | None:
    if not check.id.startswith(prefix):
        return None
    return check.id[len(prefix):] or None


def id_last_segment(check: CheckResult) -> str | None:
    """Last ``:``-separated segment of the id (e.g. the builtin of ``constraint:ex:forbidden_builtin:abs``)."""
    parts = check.id.split(":")
    if len(parts) < 2:
        return None
    return parts[-1] or None


def literal_str(snap: ValueSnapshot | None) -> str | None:
    """The Python string behind a ``str`` value snapshot, else None."""
    if snap is None or snap.type != "str":
        return None
    try:
        value = ast.literal_eval(snap.repr)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    return value if isinstance(value, str) else None


def text_pair(check: CheckResult) -> tuple[str, str] | None:
    """(expected, actual) texts of a string comparison (returned string, prompt...)."""
    ev = evidence(check)
    if ev.value_diff is not None and not ev.value_diff.equal:
        return ev.value_diff.expected, ev.value_diff.actual
    exp, act = literal_str(ev.expected_value), literal_str(ev.actual_value)
    if exp is not None and act is not None:
        return exp, act
    for exp_key, act_key in (("expected_prompt", "actual_prompt"), ("expected", "actual"), ("expected_text", "actual_text")):
        exp_v, act_v = ev.details.get(exp_key), ev.details.get(act_key)
        if isinstance(exp_v, str) and isinstance(act_v, str):
            return exp_v, act_v
    return None


def expected_text(check: CheckResult) -> str | None:
    pair = text_pair(check)
    if pair:
        return pair[0]
    ev = evidence(check)
    return detail_str(check, "expected_prompt", "expected", "prompt") or literal_str(ev.expected_value)


def stdout_diff(check: CheckResult) -> TextDiff | None:
    ev = evidence(check)
    diff = ev.stdout_diff or ev.value_diff
    return diff if diff is not None and not diff.equal else None


def changed_lines(diff: TextDiff | None) -> list[DiffLine]:
    return [line for line in diff.lines if line.op == "changed"] if diff else []


def lines_with_op(diff: TextDiff | None, op: str) -> list[DiffLine]:
    return [line for line in diff.lines if line.op == op] if diff else []


def first_difference(diff: TextDiff | None) -> DiffLine | None:
    if diff is None:
        return None
    return next((line for line in diff.lines if line.op != "equal"), None)


def stdin_lines(check: CheckResult) -> list[str]:
    stdin = evidence(check).stdin
    return stdin.splitlines() if stdin else []


def subject_path(check: CheckResult) -> str | None:
    """The path a structure/git check is about (as written in the subject when known)."""
    for prefix in _PATH_ID_PREFIXES:
        suffix = id_suffix(check, prefix)
        if suffix:
            return suffix
    explicit = detail_str(check, "expected_path", "spec_path", "path")
    if explicit:
        return explicit
    return check.file or (check.location.file if check.location else None)


def expected_and_found_paths(check: CheckResult) -> tuple[str | None, str | None]:
    """(path required by the subject, path where the file actually is) for misplaced files."""
    expected = detail_str(check, "expected_path", "spec_path", "expected") or id_suffix(check, "structure:file:")
    found = detail_str(check, "found_path", "actual_path", "found")
    if not found:
        for candidate in (check.location.file if check.location else None, check.file):
            if candidate and candidate != expected:
                found = candidate
                break
    if expected is None and check.file and check.file != found:
        expected = check.file
    return expected, found


def found_function_name(check: CheckResult, candidates: list[str] | None = None) -> str | None:
    """Name of the near-miss ``def`` for a wrong_function_name diagnosis."""
    named = detail_str(check, "found", "found_name", "actual_name", "near_miss", "candidate", "found_function")
    if named and named.isidentifier():
        return named
    if candidates and check.function:
        others = [c for c in candidates if c != check.function]
        close = difflib.get_close_matches(check.function, others, n=1, cutoff=0.6)
        if close:
            return close[0]
    for name in _IDENT_IN_QUOTES.findall(check.message):
        if name != check.function and (candidates is None or name in candidates):
            return name
    return None


def constraint_name(check: CheckResult) -> str | None:
    """Builtin / module / method / construct named by a constraint check."""
    named = detail_str(check, "name", "builtin", "module", "method", "construct")
    return named or id_last_segment(check)


def int_list(value: Any) -> list[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return [value]
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, int) and not isinstance(v, bool)]
    return []
