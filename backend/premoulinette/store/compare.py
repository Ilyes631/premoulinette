"""History comparison between two analyses, matching checks by their stable id.

* fixed: base fail/skipped/warning -> head pass
* new_failures: head fail/skipped while base was not failing (pass, warning, ... or absent)
* still_failing: fail/skipped in both
"""
from __future__ import annotations

from premoulinette.results.models import AnalysisComparison, AnalysisReport, CheckChange, CheckResult

_FAILING = frozenset({"fail", "skipped"})
_FIXABLE = frozenset({"fail", "skipped", "warning"})


def _change(check: CheckResult, before: str | None, after: str | None) -> CheckChange:
    return CheckChange(id=check.id, title=check.title, file=check.file, before=before, after=after)


def _is_fixed(before: str | None, after: str) -> bool:
    return before in _FIXABLE and after == "pass"


def compare_reports(base: AnalysisReport, head: AnalysisReport) -> AnalysisComparison:
    base_checks = {c.id: c for c in base.checks}
    head_checks = {c.id: c for c in head.checks}
    result = AnalysisComparison(
        base_id=base.id,
        head_id=head.id,
        readiness_delta=round(head.score.readiness - base.score.readiness, 1),
    )
    for cid, after in head_checks.items():
        prev = base_checks.get(cid)
        before = prev.status if prev is not None else None
        change = _change(after, before, after.status)
        if prev is None:
            result.new_checks.append(change)
        if after.status in _FAILING:
            # Anything that was not failing before (pass, warning, absent...) is a regression.
            (result.still_failing if before in _FAILING else result.new_failures).append(change)
        elif _is_fixed(before, after.status):
            result.fixed.append(change)
    for cid, prev in base_checks.items():
        if cid not in head_checks:
            result.removed_checks.append(_change(prev, prev.status, None))
    return result
