"""Per-exercise and per-file breakdown of the check list.

Checks are attached to an exercise by ``exercise_id``; checks without a (known) exercise id are
attached through the spec file they concern, so file-level checks (structure, syntax) show up in
every exercise of that file.
"""
from __future__ import annotations

from dataclasses import dataclass

from premoulinette.results.models import CheckResult, ExerciseScore, FileScore
from premoulinette.scoring.rules import (
    BEHAVIOUR_CATEGORIES,
    HEURISTIC_CATEGORY,
    ISSUE_STATUSES,
    MISSING_FILE_DIAGNOSES,
    MISSING_FUNCTION_DIAGNOSES,
    PASSED_STATUSES,
    PROGRESS_FAILING,
    PROGRESS_STATUSES,
    percent,
    worst_severity,
)
from premoulinette.spec.models import ExerciseSpec, PracticalSpec

# Check id prefixes whose suffix is the spec path the check is about.
_PATH_ID_PREFIXES = ("structure:file:", "syntax:", "git:untracked:", "git:ignored:")


@dataclass(frozen=True)
class _Located:
    check: CheckResult
    file: str | None        # spec path when it can be determined, else the raw check.file
    exercise_id: str | None  # only if it names an exercise of the spec


def locate_checks(checks: list[CheckResult], spec: PracticalSpec) -> list[_Located]:
    spec_paths = {f.path for f in spec.expected_files()}
    by_id = {e.id: e for e in spec.exercises}
    out: list[_Located] = []
    for c in checks:
        ex = by_id.get(c.exercise_id) if c.exercise_id else None
        out.append(_Located(c, _spec_file(c, spec_paths, ex), ex.id if ex else None))
    return out


def _spec_file(c: CheckResult, spec_paths: set[str], ex: ExerciseSpec | None) -> str | None:
    for prefix in _PATH_ID_PREFIXES:
        if c.id.startswith(prefix) and c.id[len(prefix):] in spec_paths:
            return c.id[len(prefix):]
    if c.file in spec_paths:
        return c.file
    if ex is not None:
        return ex.file_path
    return c.file


def missing_files(located: list[_Located]) -> set[str]:
    # Any non-pass status: an optional file may be reported missing as a warning/info.
    return {
        loc.file for loc in located
        if loc.file and loc.check.category == "structure" and loc.check.diagnosis in MISSING_FILE_DIAGNOSES
        and loc.check.status != "pass"
    }


def _counts_in_progress(c: CheckResult, *, optional_scope: bool) -> bool:
    """Checks that make up an exercise/file progress ratio.

    Heuristic tests never count. Elsewhere only mandatory or bonus checks count, except for an optional
    (neither required nor bonus) exercise/file, whose checks are all non-mandatory by design.
    """
    if c.status not in PROGRESS_STATUSES or c.category == HEURISTIC_CATEGORY:
        return False
    return c.mandatory or c.bonus or optional_scope


def _is_not_implemented(ex: ExerciseSpec, checks: list[CheckResult], file_missing: bool) -> bool:
    if file_missing:
        return True
    missing_fns: set[str] = set()
    for c in checks:
        if c.diagnosis not in MISSING_FUNCTION_DIAGNOSES or c.status not in PROGRESS_FAILING:
            continue
        if c.function:
            missing_fns.add(c.function)
        elif c.diagnosis == "bonus_not_implemented":
            return True
    return bool(ex.functions) and all(f.name in missing_fns for f in ex.functions)


def _exercise_status(counted: list[CheckResult], all_checks: list[CheckResult]) -> str:
    if not counted:
        return "warning"  # nothing could be verified for this exercise
    if not any(c.status in PROGRESS_FAILING for c in counted):
        return "warning" if any(c.status == "warning" for c in all_checks) else "pass"
    if any(c.status in PASSED_STATUSES and c.category in BEHAVIOUR_CATEGORIES for c in counted):
        return "partial"
    return "fail"


def exercise_scores(located: list[_Located], spec: PracticalSpec) -> list[ExerciseScore]:
    missing = missing_files(located)
    out: list[ExerciseScore] = []
    for ex in spec.exercises:
        mine = [
            loc.check for loc in located
            if loc.exercise_id == ex.id or (loc.exercise_id is None and loc.file == ex.file_path)
        ]
        optional = not ex.required and not ex.bonus
        counted = [c for c in mine if _counts_in_progress(c, optional_scope=optional)]
        passed = sum(1 for c in counted if c.status in PASSED_STATUSES)
        file_missing = ex.file_path in missing
        if ex.bonus and _is_not_implemented(ex, mine, file_missing):
            status = "not_implemented"
        elif file_missing:
            status = "missing"
        else:
            status = _exercise_status(counted, mine)
        out.append(ExerciseScore(
            exercise_id=ex.id,
            title=ex.title,
            file=ex.file_path,
            bonus=ex.bonus,
            required=ex.required,
            status=status,
            passed=passed,
            total=len(counted),
            score=percent(passed, len(counted)),
            issues=sum(1 for c in mine if c.status in ISSUE_STATUSES),
        ))
    return out


def file_scores(located: list[_Located], spec: PracticalSpec) -> list[FileScore]:
    missing = missing_files(located)
    out: list[FileScore] = []
    for req in spec.expected_files():
        if req.kind != "file":
            continue
        mine = [loc.check for loc in located if loc.file == req.path]
        optional = not req.required and not req.bonus
        counted = [c for c in mine if _counts_in_progress(c, optional_scope=optional)]
        passed = sum(1 for c in counted if c.status in PASSED_STATUSES)
        issues = [c for c in mine if c.status in ISSUE_STATUSES]
        out.append(FileScore(
            file=req.path,
            exercise_ids=[e.id for e in spec.exercises if e.file_path == req.path],
            present=req.path not in missing,
            passed=passed,
            total=len(counted),
            score=percent(passed, len(counted)),
            issues=len(issues),
            worst_severity=worst_severity(issues),
        ))
    return out


def is_bonus_complete(score: ExerciseScore) -> bool:
    return score.bonus and score.total > 0 and score.status in ("pass", "warning")
