"""Shared scoring vocabulary: which statuses count, category labels, percentage rounding.

See ARCHITECTURE.md, "Scoring rule (precise)":
mandatory checks = ``mandatory=True`` and status in {pass, warning, fail, skipped}; passed = pass + warning.
"""
from __future__ import annotations

from premoulinette.results.models import CheckResult

STATUSES: tuple[str, ...] = ("pass", "fail", "warning", "info", "bonus", "skipped")
SEVERITIES: tuple[str, ...] = ("critical", "major", "minor", "style")
SEVERITY_RANK: dict[str, int] = {s: i for i, s in enumerate(SEVERITIES)}

MANDATORY_STATUSES = frozenset({"pass", "warning", "fail", "skipped"})
PASSED_STATUSES = frozenset({"pass", "warning"})
FAILING_STATUSES = frozenset({"fail", "skipped"})

# Statuses that count in exercise/file progress (bonus = failing bonus item).
PROGRESS_STATUSES = frozenset({"pass", "warning", "fail", "skipped", "bonus"})
PROGRESS_FAILING = frozenset({"fail", "skipped", "bonus"})
ISSUE_STATUSES = frozenset({"fail", "skipped", "bonus", "warning"})

BEHAVIOUR_CATEGORIES = frozenset({"explicit_tests", "derived_tests", "output"})
HEURISTIC_CATEGORY = "heuristic_tests"

# Ordered (key, label) pairs of the scored categories. Heuristic tests are deliberately absent.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("structure", "Structure"),
    ("syntax", "Compilation"),
    ("functions", "Required functions"),
    ("explicit_tests", "Known tests"),
    ("derived_tests", "Derived tests"),
    ("output", "Output matching"),
    ("constraints", "Constraints"),
    ("runtime", "Import safety"),
    ("git", "Git"),
)

MISSING_FILE_DIAGNOSES = frozenset({"missing_file", "missing_bonus_file"})
MISSING_FUNCTION_DIAGNOSES = frozenset({"missing_function", "bonus_not_implemented"})


def is_mandatory(check: CheckResult) -> bool:
    """True if the check counts in the mandatory readiness.

    A check flagged ``bonus`` never blocks, even if a producer forgot to clear ``mandatory``.
    """
    return check.mandatory and not check.bonus and check.status in MANDATORY_STATUSES


def percent(passed: int, total: int) -> float | None:
    """``100 * passed / total`` rounded to 1 decimal; None when there is nothing to count.

    Never rounds an incomplete result up to 100.0 (1999/2000 -> 99.9, not 100.0).
    """
    if total <= 0:
        return None
    value = round(100.0 * passed / total, 1)
    if passed < total and value >= 100.0:
        return 99.9
    return value


def worst_severity(checks: list[CheckResult]) -> str | None:
    ranked = [c.severity for c in checks if c.severity is not None]
    return min(ranked, key=SEVERITY_RANK.__getitem__) if ranked else None
