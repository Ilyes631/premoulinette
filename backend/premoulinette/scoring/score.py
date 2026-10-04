"""Readiness scoring (ARCHITECTURE.md, "Scoring rule (precise)").

``readiness = mandatory_readiness = 100 * passed / total`` over checks with ``mandatory=True`` and
status in {pass, warning, fail, skipped}; passed = pass + warning. Heuristic and bonus checks never
change it. The result is a pre-submission indicator and never claims to be an official grade.
"""
from __future__ import annotations

from premoulinette.results.models import CategoryScore, CheckResult, ScoreSummary
from premoulinette.scoring.breakdown import exercise_scores, file_scores, is_bonus_complete, locate_checks
from premoulinette.scoring.confidence import assess_confidence
from premoulinette.scoring.rules import (
    CATEGORIES,
    FAILING_STATUSES,
    PASSED_STATUSES,
    SEVERITIES,
    STATUSES,
    is_mandatory,
    percent,
)
from premoulinette.spec.models import PracticalSpec

READY_TITLE = "READY TO SUBMIT"
NOT_READY_TITLE = "DO NOT SUBMIT YET"
READY_MESSAGE = (
    "All requirements that could be verified from the subject passed. Hidden grader tests may still exist."
)
NOTHING_VERIFIED_MESSAGE = "No mandatory requirement could be verified from the subject."
CRITICAL_SUFFIX = " Fix critical issues first."


def compute_score(
    checks: list[CheckResult], spec: PracticalSpec, *, spec_reviewed: bool, sandbox_mode: str
) -> ScoreSummary:
    mandatory = [c for c in checks if is_mandatory(c)]
    passed = sum(1 for c in mandatory if c.status in PASSED_STATUSES)
    failures = [c for c in mandatory if c.status in FAILING_STATUSES]
    readiness = percent(passed, len(mandatory)) or 0.0

    located = locate_checks(checks, spec)
    exercises = exercise_scores(located, spec)
    bonus = [e for e in exercises if e.bonus]
    bonus_passed = sum(1 for e in bonus if is_bonus_complete(e))

    confidence, reasons = assess_confidence(
        checks, spec, spec_reviewed=spec_reviewed, sandbox_mode=sandbox_mode, mandatory_total=len(mandatory)
    )
    verdict, title, message = _verdict(len(mandatory), failures)

    return ScoreSummary(
        readiness=readiness,
        mandatory_readiness=readiness,
        mandatory_passed=passed,
        mandatory_total=len(mandatory),
        mandatory_failures=len(failures),
        bonus_completion=percent(bonus_passed, len(bonus)),
        bonus_passed=bonus_passed,
        bonus_total=len(bonus),
        confidence=confidence,
        confidence_reasons=reasons,
        categories=category_scores(checks),
        exercises=exercises,
        files=file_scores(located, spec),
        counts=_counts(checks),
        verdict=verdict,
        verdict_title=title,
        verdict_message=message,
    )


def category_scores(checks: list[CheckResult]) -> list[CategoryScore]:
    out: list[CategoryScore] = []
    for key, label in CATEGORIES:
        in_category = [c for c in checks if c.category == key]
        mandatory = [c for c in in_category if is_mandatory(c)]
        if not mandatory:
            continue
        passed = sum(1 for c in mandatory if c.status in PASSED_STATUSES)
        out.append(CategoryScore(
            key=key,
            label=label,
            passed=passed,
            total=len(mandatory),
            score=percent(passed, len(mandatory)),
            failed=sum(1 for c in mandatory if c.status in FAILING_STATUSES),
            warnings=sum(1 for c in in_category if c.status == "warning"),
        ))
    return out


def _counts(checks: list[CheckResult]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES} | {s: 0 for s in SEVERITIES}
    for c in checks:
        counts[c.status] += 1
        if c.status in FAILING_STATUSES and c.severity is not None:
            counts[c.severity] += 1
    return counts


def _verdict(mandatory_total: int, failures: list[CheckResult]) -> tuple[str, str, str]:
    if mandatory_total == 0:
        # Nothing verified: claiming "ready" would be misleading.
        return "not_ready", NOT_READY_TITLE, NOTHING_VERIFIED_MESSAGE
    if not failures:
        return "ready", READY_TITLE, READY_MESSAGE
    message = f"{len(failures)} mandatory failure(s) remain."
    if any(c.severity == "critical" for c in failures):
        message += CRITICAL_SUFFIX
    return "not_ready", NOT_READY_TITLE, message
