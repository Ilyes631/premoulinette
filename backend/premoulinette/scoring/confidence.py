"""Confidence of the readiness score: how much the verified requirements cover the subject.

Starts at ``high``; each reason can only lower it. Reasons are human sentences shown in the UI.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from premoulinette.results.models import CheckResult
from premoulinette.scoring.rules import HEURISTIC_CATEGORY
from premoulinette.spec.models import Origin, PracticalSpec

Confidence = Literal["high", "medium", "low"]
_RANK: dict[str, int] = {"high": 2, "medium": 1, "low": 0}

MIN_TESTS_PER_FUNCTION = 2
LOCAL_SANDBOX_NOTE = (
    "Developer mode sandbox: student code ran locally with weaker isolation than Docker."
)


class _Assessment:
    def __init__(self) -> None:
        self.level: Confidence = "high"
        self.reasons: list[str] = []

    def lower(self, level: Confidence, reason: str) -> None:
        if _RANK[level] < _RANK[self.level]:
            self.level = level
        self.reasons.append(reason)

    def note(self, reason: str) -> None:
        self.reasons.append(reason)


def _spec_origins(spec: PracticalSpec) -> Iterator[Origin]:
    yield spec.global_constraints.origin
    for f in spec.structure.files:
        yield f.origin
    for ex in spec.exercises:
        yield ex.origin
        if ex.constraints is not None:
            yield ex.constraints.origin
        for fn in ex.functions:
            yield fn.origin
            yield from (r.origin for r in fn.rules)
            yield from (t.origin for t in fn.tests)
        if ex.script is not None:
            yield ex.script.origin
            yield from (t.origin for t in ex.script.tests)


def _test_function(c: CheckResult) -> str | None:
    """Function targeted by a test check: explicit field, else the ``<fn>#...`` test id."""
    if c.function:
        return c.function
    raw = c.test_id or (c.id[len("test:"):] if c.id.startswith("test:") else None)
    if raw and "#" in raw:
        return raw.split("#", 1)[0]
    return None


def _under_tested_functions(checks: list[CheckResult], spec: PracticalSpec) -> list[str]:
    counts: dict[tuple[str | None, str], int] = {}
    for c in checks:
        if c.category not in ("explicit_tests", "derived_tests"):
            continue
        fn = _test_function(c)
        if fn:
            counts[(c.exercise_id, fn)] = counts.get((c.exercise_id, fn), 0) + 1
    weak: list[str] = []
    for ex in spec.exercises:
        if ex.bonus or not ex.required:
            continue
        for fn in ex.functions:
            n = counts.get((ex.id, fn.name), 0) + counts.get((None, fn.name), 0)
            if n < MIN_TESTS_PER_FUNCTION:
                weak.append(fn.name)
    return weak


def _explicit_test_count(checks: list[CheckResult]) -> int:
    return sum(1 for c in checks if c.category in ("explicit_tests", "output") and c.id.startswith("test:"))


def assess_confidence(
    checks: list[CheckResult],
    spec: PracticalSpec,
    *,
    spec_reviewed: bool,
    sandbox_mode: str,
    mandatory_total: int,
) -> tuple[Confidence, list[str]]:
    a = _Assessment()

    if mandatory_total == 0:
        a.lower("low", "No mandatory requirement could be verified.")
    if _explicit_test_count(checks) == 0:
        a.lower("low", "No explicit test was found in the subject: behaviour was not checked against official examples.")

    reviewed = spec_reviewed or spec.metadata.reviewed_by_user
    ai_items = sum(1 for o in _spec_origins(spec) if o.provenance == "ai_extracted")
    if ai_items and not reviewed:
        a.lower("medium", f"{ai_items} requirement(s) were extracted by AI and have not been reviewed.")

    weak = _under_tested_functions(checks, spec)
    if weak:
        a.lower(
            "medium",
            f"{len(weak)} mandatory function(s) have fewer than {MIN_TESTS_PER_FUNCTION} explicit or derived tests: "
            + ", ".join(weak) + ".",
        )

    heuristic_warnings = sum(1 for c in checks if c.category == HEURISTIC_CATEGORY and c.status == "warning")
    if heuristic_warnings:
        a.lower(
            "medium",
            f"{heuristic_warnings} heuristic test warning(s): extra cases that are not official requirements failed.",
        )

    if spec.notes:
        a.lower(
            "medium",
            f"The subject parser left {len(spec.notes)} note(s) about ambiguous or unformalized parts of the subject.",
        )

    if sandbox_mode == "local":
        a.note(LOCAL_SANDBOX_NOTE)

    return a.level, a.reasons
