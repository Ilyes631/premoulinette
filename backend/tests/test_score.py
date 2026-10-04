"""Scoring rule tests on small hand-built check lists (ARCHITECTURE.md, "Scoring rule (precise)")."""
from __future__ import annotations

import pytest

from premoulinette.results.models import CheckResult
from premoulinette.scoring.score import (
    NOT_READY_TITLE,
    NOTHING_VERIFIED_MESSAGE,
    READY_MESSAGE,
    READY_TITLE,
    compute_score,
)
from premoulinette.spec.models import (
    BehaviorRule,
    ExerciseSpec,
    FunctionSignature,
    FunctionSpec,
    Origin,
    PracticalSpec,
    SpecMetadata,
)
from report_factory import make_report

A, B, G = "pkg/alpha.py", "pkg/beta.py", "pkg/bonus/gamma.py"


def _fn(name: str, *, rules: list[BehaviorRule] | None = None) -> FunctionSpec:
    return FunctionSpec(signature=FunctionSignature(name=name), rules=rules or [])


def mini_spec(*, bonus: bool = True, notes: list[str] | None = None, ai_rule: bool = False,
              reviewed: bool = False) -> PracticalSpec:
    rules = [BehaviorRule(when="x > 0", returns="True", origin=Origin(provenance="ai_extracted", confidence=0.5))] \
        if ai_rule else None
    exercises = [
        ExerciseSpec(id="alpha", title="Alpha", file_path=A, functions=[_fn("f", rules=rules)]),
        ExerciseSpec(id="beta", title="Beta", file_path=B, functions=[_fn("g")]),
    ]
    if bonus:
        exercises.append(ExerciseSpec(id="gamma", title="Gamma", file_path=G, bonus=True, functions=[_fn("h")]))
    return PracticalSpec(metadata=SpecMetadata(title="Mini", reviewed_by_user=reviewed), exercises=exercises,
                         notes=notes or [])


def chk(cid: str, status: str = "pass", category: str = "explicit_tests", **kw: object) -> CheckResult:
    kw.setdefault("severity", "major" if status in ("fail", "warning") else None)
    return CheckResult(id=cid, category=category, status=status, title=cid, message=f"{cid} {status}", **kw)


def bonus_chk(cid: str, status: str = "pass", category: str = "explicit_tests", **kw: object) -> CheckResult:
    return chk(cid, status, category, mandatory=False, bonus=True, exercise_id="gamma", file=G, **kw)


def all_pass() -> list[CheckResult]:
    return [
        chk(f"structure:file:{A}", category="structure", file=A),
        chk(f"structure:file:{B}", category="structure", file=B),
        chk(f"syntax:{A}", category="syntax", file=A),
        chk(f"syntax:{B}", category="syntax", file=B),
        chk("function:alpha:f", category="functions", exercise_id="alpha", function="f", file=A),
        chk("function:beta:g", category="functions", exercise_id="beta", function="g", file=B),
        chk("test:f#ex1", exercise_id="alpha", function="f", file=A),
        chk("test:f#ex2", exercise_id="alpha", function="f", file=A),
        chk("test:g#ex1", exercise_id="beta", function="g", file=B),
        chk("test:g#derived1", category="derived_tests", exercise_id="beta", function="g", file=B),
    ]


def score(checks: list[CheckResult], spec: PracticalSpec | None = None, *, reviewed: bool = True,
          sandbox: str = "docker"):
    return compute_score(checks, spec or mini_spec(bonus=False), spec_reviewed=reviewed, sandbox_mode=sandbox)


# ---- readiness & verdict --------------------------------------------------------------------------

def test_all_mandatory_pass_is_ready() -> None:
    s = score(all_pass())
    assert s.readiness == s.mandatory_readiness == 100.0
    assert (s.mandatory_passed, s.mandatory_total, s.mandatory_failures) == (10, 10, 0)
    assert s.verdict == "ready"
    assert s.verdict_title == READY_TITLE == "READY TO SUBMIT"
    assert s.verdict_message == READY_MESSAGE
    assert "Hidden grader tests may still exist" in s.verdict_message
    assert s.confidence == "high" and s.confidence_reasons == []
    assert s.bonus_completion is None and s.bonus_total == 0


def test_mandatory_failure_is_not_ready() -> None:
    checks = all_pass()
    checks[6] = chk("test:f#ex1", "fail", exercise_id="alpha", function="f", file=A, severity="major")
    s = score(checks)
    assert s.verdict == "not_ready"
    assert s.verdict_title == NOT_READY_TITLE == "DO NOT SUBMIT YET"
    assert s.verdict_message == "1 mandatory failure(s) remain."
    assert s.mandatory_failures == 1
    assert s.readiness == 90.0


def test_critical_failure_adds_fix_critical_first() -> None:
    checks = all_pass()
    checks[0] = chk(f"structure:file:{A}", "fail", "structure", file=A, severity="critical", diagnosis="missing_file")
    checks[6] = chk("test:f#ex1", "skipped", exercise_id="alpha", function="f", file=A,
                    blocked_by=f"structure:file:{A}")
    s = score(checks)
    assert s.verdict_message == "2 mandatory failure(s) remain. Fix critical issues first."


def test_bonus_checks_never_count_in_mandatory_readiness() -> None:
    spec = mini_spec()
    checks = all_pass() + [
        bonus_chk(f"structure:file:{G}", "bonus", "structure", diagnosis="missing_bonus_file"),
        bonus_chk("test:h#ex1", "bonus", blocked_by=f"structure:file:{G}"),
        # Producer inconsistency (mandatory left True on a bonus check): must still not block.
        chk("test:h#ex2", "fail", exercise_id="gamma", file=G, bonus=True, mandatory=True),
    ]
    s = score(checks, spec)
    assert s.readiness == 100.0
    assert s.mandatory_total == 10
    assert s.verdict == "ready"
    assert (s.bonus_completion, s.bonus_passed, s.bonus_total) == (0.0, 0, 1)


def test_heuristic_warnings_do_not_change_readiness_but_lower_confidence() -> None:
    checks = all_pass() + [
        chk("test:f#heur1", "warning", "heuristic_tests", mandatory=False, exercise_id="alpha", function="f",
            origin=Origin(provenance="heuristic", confidence=0.5)),
        chk("test:g#heur1", "warning", "heuristic_tests", mandatory=False, exercise_id="beta", function="g",
            origin=Origin(provenance="heuristic", confidence=0.5)),
    ]
    s = score(checks)
    assert s.readiness == 100.0 and s.mandatory_total == 10
    assert s.verdict == "ready"
    assert s.confidence == "medium"
    assert any("2 heuristic test warning(s)" in r for r in s.confidence_reasons)
    assert "heuristic_tests" not in [c.key for c in s.categories]


def test_skipped_counts_as_not_passed() -> None:
    checks = all_pass()[:3] + [chk("test:f#ex1", "skipped", exercise_id="alpha", blocked_by="syntax:x")]
    s = score(checks)
    assert (s.mandatory_passed, s.mandatory_total, s.mandatory_failures) == (3, 4, 1)
    assert s.readiness == 75.0
    assert s.verdict == "not_ready"


def test_warning_counts_as_passed() -> None:
    checks = all_pass() + [chk("import_effects:alpha", "warning", "runtime", exercise_id="alpha", file=A,
                               diagnosis="import_side_effects")]
    s = score(checks)
    assert (s.mandatory_passed, s.mandatory_total) == (11, 11)
    assert s.readiness == 100.0 and s.verdict == "ready"
    runtime = next(c for c in s.categories if c.key == "runtime")
    assert (runtime.passed, runtime.total, runtime.warnings, runtime.score) == (1, 1, 1, 100.0)


def test_info_checks_are_ignored() -> None:
    s = score(all_pass() + [chk("structure:extra:pkg/notes.py", "info", "structure", file="pkg/notes.py")])
    assert s.mandatory_total == 10


@pytest.mark.parametrize(("passed", "failed", "expected"), [(2, 1, 66.7), (1, 2, 33.3), (1999, 1, 99.9), (0, 3, 0.0)])
def test_readiness_rounding_never_reaches_100_with_failures(passed: int, failed: int, expected: float) -> None:
    checks = [chk(f"test:f#p{i}") for i in range(passed)] + [chk(f"test:f#f{i}", "fail") for i in range(failed)]
    assert score(checks).readiness == expected


def test_no_mandatory_check_is_not_ready_and_low_confidence() -> None:
    s = score([])
    assert s.readiness == 0.0 and s.mandatory_total == 0
    assert s.verdict == "not_ready" and s.verdict_message == NOTHING_VERIFIED_MESSAGE
    assert s.confidence == "low"


# ---- categories, exercises, files, counts ---------------------------------------------------------

def test_categories_are_ordered_labelled_and_only_present_ones() -> None:
    checks = all_pass() + [
        chk("constraint:alpha:forbidden_builtin:abs", "fail", "constraints", exercise_id="alpha", file=A,
            severity="critical"),
        chk("git:dirty", "warning", "git", severity="minor"),
    ]
    s = score(checks)
    assert [(c.key, c.label) for c in s.categories] == [
        ("structure", "Structure"), ("syntax", "Compilation"), ("functions", "Required functions"),
        ("explicit_tests", "Known tests"), ("derived_tests", "Derived tests"), ("constraints", "Constraints"),
        ("git", "Git"),
    ]
    constraints = next(c for c in s.categories if c.key == "constraints")
    assert (constraints.passed, constraints.total, constraints.failed, constraints.score) == (0, 1, 1, 0.0)


def test_all_category_labels() -> None:
    cats = ["structure", "syntax", "functions", "explicit_tests", "derived_tests", "output", "constraints",
            "runtime", "git"]
    s = score([chk(f"x:{c}", category=c) for c in cats])
    assert [c.label for c in s.categories] == [
        "Structure", "Compilation", "Required functions", "Known tests", "Derived tests", "Output matching",
        "Constraints", "Import safety", "Git",
    ]


def test_exercise_statuses() -> None:
    spec = mini_spec()
    checks = [
        # alpha: structure + one passing test + one failing test -> partial
        chk(f"structure:file:{A}", category="structure", file=A),
        chk("test:f#ex1", exercise_id="alpha", function="f", file=A),
        chk("test:f#ex2", "fail", exercise_id="alpha", function="f", file=A),
        # beta: file missing -> missing
        chk(f"structure:file:{B}", "fail", "structure", file=B, severity="critical", diagnosis="missing_file"),
        chk("test:g#ex1", "skipped", exercise_id="beta", function="g", blocked_by=f"structure:file:{B}"),
        # gamma (bonus): file present but function missing -> not_implemented
        bonus_chk(f"structure:file:{G}", category="structure"),
        bonus_chk("function:gamma:h", "bonus", "functions", function="h", diagnosis="missing_function"),
    ]
    s = score(checks, spec)
    status = {e.exercise_id: e for e in s.exercises}
    assert status["alpha"].status == "partial" and (status["alpha"].passed, status["alpha"].total) == (2, 3)
    assert status["beta"].status == "missing" and status["beta"].issues == 2
    assert status["gamma"].status == "not_implemented" and status["gamma"].bonus
    assert s.bonus_completion == 0.0


def test_exercise_fail_pass_and_warning_statuses() -> None:
    checks = [
        chk(f"structure:file:{A}", category="structure", file=A),
        chk("test:f#ex1", "fail", exercise_id="alpha", function="f"),
        chk("test:f#ex2", "fail", exercise_id="alpha", function="f"),
        chk(f"structure:file:{B}", category="structure", file=B),
        chk("test:g#ex1", exercise_id="beta", function="g"),
        chk("test:g#heur1", "warning", "heuristic_tests", mandatory=False, exercise_id="beta", function="g"),
    ]
    status = {e.exercise_id: e for e in score(checks).exercises}
    assert status["alpha"].status == "fail"     # no behavioural test passes
    assert status["beta"].status == "warning"   # all counted checks pass, a heuristic warning remains
    assert (status["beta"].passed, status["beta"].total) == (2, 2)  # heuristic checks are not counted


def test_bonus_completion_counts_fully_passing_bonus_exercises() -> None:
    checks = all_pass() + [bonus_chk(f"structure:file:{G}", category="structure"), bonus_chk("test:h#ex1"),
                           bonus_chk("test:h#ex2")]
    s = score(checks, mini_spec())
    assert (s.bonus_completion, s.bonus_passed, s.bonus_total) == (100.0, 1, 1)
    assert next(e for e in s.exercises if e.exercise_id == "gamma").status == "pass"


def test_optional_exercise_progress_counts_its_non_mandatory_checks() -> None:
    opt = "pkg/extra/delta.py"
    spec = mini_spec(bonus=False)
    spec.exercises.append(ExerciseSpec(id="delta", title="Delta", file_path=opt, required=False,
                                       functions=[_fn("d")]))
    optional = {"mandatory": False, "exercise_id": "delta", "file": opt}
    checks = all_pass() + [
        chk(f"structure:file:{opt}", category="structure", mandatory=False, file=opt),
        chk("test:d#ex1", function="d", **optional),
        chk("test:d#ex2", "fail", function="d", **optional),
    ]
    s = score(checks, spec)
    assert (s.mandatory_total, s.verdict) == (10, "ready")  # optional checks never block
    delta = next(e for e in s.exercises if e.exercise_id == "delta")
    assert (delta.status, delta.passed, delta.total) == ("partial", 2, 3)
    assert next(f for f in s.files if f.file == opt).total == 3


def test_optional_file_reported_missing_as_warning_is_missing() -> None:
    opt = "pkg/extra/delta.py"
    spec = mini_spec(bonus=False)
    spec.exercises.append(ExerciseSpec(id="delta", title="Delta", file_path=opt, required=False))
    checks = all_pass() + [chk(f"structure:file:{opt}", "warning", "structure", mandatory=False, file=opt,
                               severity="minor", diagnosis="missing_file")]
    s = score(checks, spec)
    assert next(e for e in s.exercises if e.exercise_id == "delta").status == "missing"
    assert not next(f for f in s.files if f.file == opt).present


def test_files_breakdown() -> None:
    checks = all_pass()
    checks[1] = chk(f"structure:file:{B}", "fail", "structure", file=B, severity="critical", diagnosis="missing_file")
    checks.append(chk("returns:alpha:f", "fail", "functions", exercise_id="alpha", function="f", severity="minor"))
    files = {f.file: f for f in score(checks).files}
    assert set(files) == {A, B}
    assert files[A].present and files[A].exercise_ids == ["alpha"]
    assert files[A].worst_severity == "minor" and files[A].issues == 1
    assert not files[B].present and files[B].worst_severity == "critical"


def test_counts_by_status_and_failing_severity() -> None:
    checks = all_pass() + [
        chk("a", "fail", severity="critical"), chk("b", "fail", severity="minor"),
        chk("c", "skipped", severity=None), chk("d", "warning", severity="major"), chk("e", "info"),
        bonus_chk("f", "bonus", severity="critical"),
    ]
    counts = score(checks, mini_spec()).counts
    assert counts["pass"] == 10 and counts["fail"] == 2 and counts["skipped"] == 1
    assert counts["warning"] == 1 and counts["info"] == 1 and counts["bonus"] == 1
    # severities only of failing (fail/skipped) checks
    assert (counts["critical"], counts["major"], counts["minor"], counts["style"]) == (1, 0, 1, 0)


# ---- confidence -----------------------------------------------------------------------------------

def test_no_explicit_test_gives_low_confidence() -> None:
    checks = [c for c in all_pass() if c.category != "explicit_tests"]
    s = score(checks)
    assert s.confidence == "low"
    assert any("No explicit test" in r for r in s.confidence_reasons)


def test_unreviewed_ai_extracted_items_lower_confidence() -> None:
    spec = mini_spec(bonus=False, ai_rule=True)
    unreviewed = compute_score(all_pass(), spec, spec_reviewed=False, sandbox_mode="docker")
    assert unreviewed.confidence == "medium"
    assert any("extracted by AI" in r for r in unreviewed.confidence_reasons)
    reviewed = compute_score(all_pass(), spec, spec_reviewed=True, sandbox_mode="docker")
    assert reviewed.confidence == "high"


def test_function_with_fewer_than_two_tests_lowers_confidence() -> None:
    checks = [c for c in all_pass() if c.id != "test:g#derived1"]
    s = score(checks)
    assert s.confidence == "medium"
    assert any("fewer than 2" in r and "g." in r for r in s.confidence_reasons)


def test_test_function_is_derived_from_test_id_when_function_field_missing() -> None:
    checks = [c.model_copy(update={"function": None}) if c.id.startswith("test:") else c for c in all_pass()]
    assert score(checks).confidence == "high"


def test_local_sandbox_adds_note_without_downgrade() -> None:
    s = score(all_pass(), sandbox="local")
    assert s.confidence == "high"
    assert any("Developer mode sandbox" in r for r in s.confidence_reasons)


def test_parser_notes_lower_confidence() -> None:
    s = score(all_pass(), mini_spec(bonus=False, notes=["Could not formalize the rule about negative speeds."]))
    assert s.confidence == "medium"
    assert any("1 note(s)" in r for r in s.confidence_reasons)


def test_lowest_level_wins() -> None:
    checks = [c for c in all_pass() if c.category != "explicit_tests"]
    s = score(checks, mini_spec(bonus=False, notes=["ambiguous"]))
    assert s.confidence == "low"
    assert len(s.confidence_reasons) >= 2


# ---- realistic reports ----------------------------------------------------------------------------

def test_factory_buggy_report_is_not_ready() -> None:
    s = make_report().score
    assert s.verdict == "not_ready"
    assert s.verdict_message.endswith(" Fix critical issues first.")
    assert s.mandatory_failures == s.counts["fail"] + s.counts["skipped"]
    assert 0 < s.readiness < 100
    by_id = {e.exercise_id: e.status for e in s.exercises}
    assert by_id["kelvin"] == "pass"
    assert by_id["mission_clock"] == "warning"
    assert by_id["countdown"] == "not_implemented"
    assert by_id["emoji_grade"] == "pass"
    assert s.bonus_passed == 1 and s.bonus_total == 3 and s.bonus_completion == 33.3


def test_factory_passing_report_is_ready_with_high_confidence() -> None:
    s = make_report(variant="fixed").score
    assert s.verdict == "ready" and s.readiness == 100.0
    assert s.confidence == "high" and s.confidence_reasons == []
    assert s.bonus_completion == 100.0
