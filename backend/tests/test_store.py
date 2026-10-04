"""Local store tests: records round-trip, history order, numbering, comparison, settings."""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from premoulinette.results.models import AnalysisReport, CheckResult
from premoulinette.store.db import ProjectRecord, Settings, Store, SubjectRecord
from report_factory import buggy_checks, make_report, make_spec, passing_checks

T0 = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "premoulinette.db"


@pytest.fixture
def store(db_path: Path) -> Iterator[Store]:
    s = Store(db_path)
    yield s
    s.close()


def subject(sid: str = "subject-1", *, created_at: datetime = T0, **kw: object) -> SubjectRecord:
    spec = make_spec()
    return SubjectRecord(id=sid, title=spec.metadata.title, source_name="subject_demo.html", spec=spec,
                         document_text="TP 1 ...", media_type="html", created_at=created_at, updated_at=created_at,
                         **kw)


def project(pid: str = "project-1", *, created_at: datetime = T0) -> ProjectRecord:
    return ProjectRecord(id=pid, name="mysteryinc_buggy", source_kind="demo", source_path="demo/projects/x",
                         snapshot_path="/tmp/snap/1", file_count=14, python_files=10, created_at=created_at)


def analysis(aid: str, minutes: int, *, subject_id: str = "subject-1", project_id: str = "project-1",
             number: int = 1, variant: str = "buggy", checks: list[CheckResult] | None = None) -> AnalysisReport:
    return make_report(checks, variant=variant, report_id=aid, number=number, subject_id=subject_id,
                       project_id=project_id, created_at=T0 + timedelta(minutes=minutes))


# ---- subjects / projects --------------------------------------------------------------------------

def test_creates_database_with_wal(db_path: Path, store: Store) -> None:
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_subject_round_trip_and_listing(store: Store) -> None:
    rec = subject(document_html="<h1>TP</h1>", parse_warnings=["no deadline"], raw_path="subjects/s1.html")
    store.save_subject(rec)
    assert store.get_subject("subject-1") == rec
    assert store.get_subject("missing") is None
    store.save_subject(subject("subject-2", created_at=T0 + timedelta(hours=1)))
    assert [s.id for s in store.list_subjects()] == ["subject-2", "subject-1"]   # newest first


def test_save_subject_upserts(store: Store) -> None:
    store.save_subject(subject())
    store.save_subject(subject().model_copy(update={"title": "Renamed"}))
    assert len(store.list_subjects()) == 1
    assert store.get_subject("subject-1").title == "Renamed"


def test_update_spec(store: Store) -> None:
    store.save_subject(subject(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    spec = make_spec()
    spec.metadata.title = "TP 1 — reviewed"
    spec.metadata.reviewed_by_user = True
    updated = store.update_spec("subject-1", spec)
    assert updated is not None
    reloaded = store.get_subject("subject-1")
    assert reloaded == updated
    assert reloaded.spec.metadata.reviewed_by_user is True
    assert reloaded.title == "TP 1 — reviewed"
    assert reloaded.updated_at > reloaded.created_at
    assert store.update_spec("missing", spec) is None


def test_project_round_trip(store: Store) -> None:
    store.save_project(project())
    store.save_project(project("project-2", created_at=T0 + timedelta(minutes=5)))
    assert store.get_project("project-1") == project()
    assert store.get_project("missing") is None
    assert [p.id for p in store.list_projects()] == ["project-2", "project-1"]


def test_records_use_timezone_aware_utc() -> None:
    naive = subject(created_at=datetime(2026, 10, 3, 9, 0))
    assert naive.created_at.tzinfo is not None and naive.created_at.utcoffset() == timedelta(0)
    paris = timezone(timedelta(hours=2))
    rec = project(created_at=datetime(2026, 10, 3, 11, 0, tzinfo=paris))
    assert rec.created_at == T0 and rec.created_at.utcoffset() == timedelta(0)
    assert SubjectRecord.model_fields["created_at"].default_factory().tzinfo is not None


# ---- analyses -------------------------------------------------------------------------------------

def test_analysis_round_trip(store: Store) -> None:
    report = analysis("a1", 0)
    store.save_analysis(report)
    assert store.get_analysis("a1") == report
    assert store.get_analysis("missing") is None


def test_history_is_newest_first_and_filterable(store: Store) -> None:
    # Saved out of chronological order on purpose.
    for aid, minutes, sid in [("a2", 10, "subject-1"), ("a1", 0, "subject-1"), ("a3", 20, "subject-1"),
                              ("b1", 5, "subject-2")]:
        store.save_analysis(analysis(aid, minutes, subject_id=sid))
    assert [a.id for a in store.list_analyses()] == ["a3", "a2", "b1", "a1"]
    assert [a.id for a in store.list_analyses(subject_id="subject-1")] == ["a3", "a2", "a1"]
    assert [a.id for a in store.list_analyses(subject_id="subject-2", project_id="project-1")] == ["b1"]
    assert store.list_analyses(project_id="other") == []
    assert [a.id for a in store.list_analyses(limit=2)] == ["a3", "a2"]


def test_list_item_mirrors_report_summary(store: Store) -> None:
    report = analysis("a1", 0, number=4)
    store.save_analysis(report)
    (item,) = store.list_analyses()
    s = report.score
    assert (item.id, item.number, item.subject_id, item.project_id) == ("a1", 4, "subject-1", "project-1")
    assert item.created_at == report.created_at and item.created_at.tzinfo is not None
    assert (item.subject_title, item.project_name) == (report.subject.title, report.project.name)
    assert (item.readiness, item.mandatory_readiness, item.bonus_completion) == (
        s.readiness, s.mandatory_readiness, s.bonus_completion)
    assert (item.verdict, item.mandatory_failures) == (s.verdict, s.mandatory_failures)


def test_next_number_counts_analyses_of_the_pair(store: Store) -> None:
    assert store.next_number("subject-1", "project-1") == 1
    store.save_analysis(analysis("a1", 0, number=1))
    store.save_analysis(analysis("a2", 1, number=2))
    store.save_analysis(analysis("x1", 2, subject_id="subject-2", number=1))
    assert store.next_number("subject-1", "project-1") == 3
    assert store.next_number("subject-2", "project-1") == 2
    assert store.next_number("subject-1", "project-2") == 1
    assert store.delete_analysis("a1") is True
    assert store.next_number("subject-1", "project-1") == 3   # never reuses a number


def test_delete_analysis(store: Store) -> None:
    store.save_analysis(analysis("a1", 0))
    assert store.delete_analysis("a1") is True
    assert store.get_analysis("a1") is None
    assert store.delete_analysis("a1") is False


def test_compare(store: Store) -> None:
    base = analysis("base", 0)
    head_checks = {c.id: c for c in passing_checks()}
    still = next(c for c in buggy_checks() if c.id == "test:average_speed#ex2")
    head_checks[still.id] = still                                                        # still failing
    head_checks["test:to_kelvin#ex1"] = head_checks["test:to_kelvin#ex1"].model_copy(
        update={"status": "fail", "severity": "major"})                                    # regression
    head_checks["test:brand_new#ex1"] = CheckResult(id="test:brand_new#ex1", category="explicit_tests",
                                                    status="fail", severity="major", title="New", message="new")
    head_checks["test:another#ex1"] = CheckResult(id="test:another#ex1", category="explicit_tests",
                                                  status="pass", title="Another", message="ok")
    head_checks["import_effects:mission_clock"] = head_checks["import_effects:mission_clock"].model_copy(
        update={"status": "warning", "severity": "major"})                                 # stays a warning
    head = analysis("head", 30, checks=list(head_checks.values()), number=2)
    store.save_analysis(base)
    store.save_analysis(head)

    cmp = store.compare("base", "head")
    assert (cmp.base_id, cmp.head_id) == ("base", "head")
    assert cmp.readiness_delta == round(head.score.readiness - base.score.readiness, 1)

    fixed = {c.id: c for c in cmp.fixed}
    assert {"test:is_safe#ex1", "test:is_safe#ex2", "test:landing_grade#ex2", "test:launch_sequence#session1",
            "structure:file:MysteryInc/FirstLaunch/FIXME2.py"} <= set(fixed)
    assert (fixed["test:is_safe#ex1"].before, fixed["test:is_safe#ex1"].after) == ("fail", "pass")
    assert "test:mission_clock#heur1" in fixed          # warning -> pass
    assert "import_effects:mission_clock" not in fixed  # warning -> warning
    assert "test:countdown#session1" not in fixed       # bonus -> pass is not a mandatory fix

    new_failures = {c.id: c for c in cmp.new_failures}
    assert set(new_failures) == {"test:to_kelvin#ex1", "test:brand_new#ex1"}
    assert (new_failures["test:to_kelvin#ex1"].before, new_failures["test:brand_new#ex1"].before) == ("pass", None)
    assert [c.id for c in cmp.still_failing] == ["test:average_speed#ex2"]
    assert {c.id for c in cmp.new_checks} == {"test:brand_new#ex1", "test:another#ex1"}
    removed = {c.id: c for c in cmp.removed_checks}
    assert {"returns:safe_speed:is_safe", "git:dirty", "git:untracked:MysteryInc/FirstLaunch/launch_sequence.py"} \
        <= set(removed)
    assert removed["git:dirty"].after is None and removed["git:dirty"].before == "warning"


def test_compare_warning_to_fail_is_a_new_failure(store: Store) -> None:
    def with_status(status: str) -> list[CheckResult]:
        return [c.model_copy(update={"status": status, "severity": "major"}) if c.id == "import_effects:kelvin"
                else c for c in passing_checks()]

    store.save_analysis(analysis("base", 0, checks=with_status("warning")))
    store.save_analysis(analysis("head", 1, checks=with_status("fail")))
    cmp = store.compare("base", "head")
    assert [(c.id, c.before, c.after) for c in cmp.new_failures] == [("import_effects:kelvin", "warning", "fail")]
    assert cmp.fixed == [] and cmp.still_failing == []
    assert cmp.readiness_delta < 0


def test_compare_fixed_requires_head_pass(store: Store) -> None:
    def with_status(status: str) -> list[CheckResult]:
        return [c.model_copy(update={"status": status, "severity": None if status == "pass" else "major"})
                if c.id == "import_effects:kelvin" else c for c in passing_checks()]

    store.save_analysis(analysis("fail", 0, checks=with_status("fail")))
    store.save_analysis(analysis("warn", 1, checks=with_status("warning")))
    store.save_analysis(analysis("pass", 2, checks=with_status("pass")))
    fail_to_warning = store.compare("fail", "warn")
    assert fail_to_warning.fixed == [] and fail_to_warning.new_failures == [] and fail_to_warning.still_failing == []
    assert fail_to_warning.readiness_delta > 0
    assert [(c.id, c.before, c.after) for c in store.compare("fail", "pass").fixed] == [
        ("import_effects:kelvin", "fail", "pass")]


def test_compare_unknown_analysis_raises(store: Store) -> None:
    store.save_analysis(analysis("a1", 0))
    with pytest.raises(KeyError):
        store.compare("a1", "missing")
    with pytest.raises(KeyError):
        store.compare("missing", "a1")


# ---- settings -------------------------------------------------------------------------------------

def test_settings_default_then_persisted(db_path: Path, store: Store) -> None:
    assert store.get_settings() == Settings()
    custom = Settings(sandbox_mode="local", local_mode_acknowledged=True, ai_enabled=True,
                      anthropic_api_key="sk-test-local", explanation_language="en", default_timeout_s=8.0)
    store.save_settings(custom)
    store.save_settings(custom.model_copy(update={"docker_image": "python:3.13-slim"}))
    store.close()
    with Store(db_path) as reopened:
        loaded = reopened.get_settings()
    assert loaded == custom.model_copy(update={"docker_image": "python:3.13-slim"})
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 1   # single row
    finally:
        conn.close()


def test_unreadable_settings_fall_back_to_defaults(db_path: Path, store: Store) -> None:
    store.save_settings(Settings(ai_enabled=True))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE settings SET data = ?", ('{"sandbox_mode": "quantum"}',))
        conn.commit()
    finally:
        conn.close()
    assert store.get_settings() == Settings()


def test_settings_defaults_match_contract() -> None:
    s = Settings()
    assert (s.sandbox_mode, s.local_mode_acknowledged, s.docker_image) == ("auto", False, "python:3.12-slim")
    assert (s.ai_enabled, s.ai_model, s.ai_consent_subject, s.ai_consent_code) == (
        False, "claude-opus-5-5", False, False)
    assert (s.anthropic_api_key, s.explanation_language, s.default_timeout_s) == (None, "fr", 5.0)


# ---- persistence & threads ------------------------------------------------------------------------

def test_data_survives_reopen(db_path: Path, store: Store) -> None:
    subj, proj, report = subject(), project(), analysis("a1", 0)
    store.save_subject(subj)
    store.save_project(proj)
    store.save_analysis(report)
    store.close()
    with Store(db_path) as reopened:
        assert reopened.get_subject("subject-1") == subj
        assert reopened.get_project("project-1") == proj
        assert reopened.get_analysis("a1") == report


def test_concurrent_writes_from_threads(store: Store) -> None:
    report = analysis("seed", 0)
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            for i in range(5):
                store.save_analysis(report.model_copy(update={"id": f"t{n}-{i}"}))
                store.list_analyses(limit=5)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(store.list_analyses(limit=100)) == 30
