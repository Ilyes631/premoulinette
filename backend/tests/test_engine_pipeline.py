from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from premoulinette.engine.pipeline import STAGES, AnalysisError, dedupe_checks, normalize_check_files, run_analysis
from premoulinette.engine.sandbox_select import NO_DOCKER_MESSAGE
from premoulinette.results.models import CheckResult
from premoulinette.store.db import ProjectRecord, Settings, Store, SubjectRecord
from test_api_fakes import FakeDockerStatus, make_project_dir, make_spec
from test_engine_fakes import FakeWorld, fake_evaluate_function, make_world

LOCAL = Settings(sandbox_mode="local", local_mode_acknowledged=True)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "db.sqlite")
    yield s
    s.close()


@pytest.fixture
def subject(store: Store) -> SubjectRecord:
    rec = SubjectRecord(id="subj", title="Fake TP", source_name="s.html", spec=make_spec(), media_type="html")
    store.save_subject(rec)
    return rec


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return make_project_dir(tmp_path / "student")


def path_project(store: Store, source: Path, kind: str = "path") -> ProjectRecord:
    rec = ProjectRecord(id="proj", name="student", source_kind=kind, source_path=str(source), snapshot_path=str(source))
    store.save_project(rec)
    return rec


class Progress:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def __call__(self, stage: str, fraction: float) -> None:
        self.calls.append((stage, fraction))

    @property
    def stages(self) -> list[str]:
        return list(dict.fromkeys(s for s, _ in self.calls))


def analyze(world: FakeWorld, subject: SubjectRecord, project: ProjectRecord, store: Store, tmp_path: Path,
            settings: Settings = LOCAL, progress: Progress | None = None) -> Any:
    return run_analysis(subject, project, settings, store, progress or Progress(),
                        deps=world.deps, snapshots_dir=tmp_path / "snapshots")


def by_id(report: Any) -> dict[str, CheckResult]:
    return {c.id: c for c in report.checks}


def test_full_run(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    world = make_world()
    progress = Progress()
    report = analyze(world, subject, path_project(store, source), store, tmp_path, progress=progress)

    # stages reported in documented order, monotonic, ending at 1.0
    assert progress.stages == [k for k, _ in STAGES]
    fractions = [f for _, f in progress.calls]
    assert fractions == sorted(fractions) and fractions[-1] == 1.0

    # persisted, numbered per (subject, project)
    assert store.get_analysis(report.id) is not None
    assert report.number == 1
    assert analyze(world, subject, store.get_project("proj"), store, tmp_path).number == 2

    checks = by_id(report)
    assert checks["test:is_safe#ex1"].status == "pass"
    assert checks["test:is_safe#derived1"].status == "pass"
    assert checks["test:hello#session1"].status == "pass"
    assert checks["import_effects:safe_speed"].status == "pass"
    # absent exercise: file missing -> structure fail, its test skipped and blocked by that check
    assert checks["structure:file:pkg/absent.py"].status == "fail"
    assert checks["test:f#ex1"].status == "skipped"
    assert checks["test:f#ex1"].blocked_by == "structure:file:pkg/absent.py"
    assert report.score.verdict == "not_ready"

    plan, root = world.sandbox.calls[0]
    assert {j.id for j in plan.jobs} == {"import:safe_speed", "is_safe#ex1", "is_safe#ex2", "is_safe#derived1", "hello#session1"}
    assert root.is_relative_to(tmp_path / "snapshots")
    assert world.factory.requested[0] == ("local", "python:3.12-slim")
    assert report.sandbox.mode == "local"
    assert report.sandbox.python_version == "3.12.7"
    assert report.subject.id == "subj" and report.project.id == "proj"
    assert report.spec == subject.spec
    assert world.fixes_calls == [len(report.checks)] * 2       # once per analysis, on the final check list


def test_explicit_tests_are_evaluated_before_derived_ones(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    order: list[tuple[str, str]] = []
    progress = Progress()

    def spy(gen: Any, res: Any, ctx: Any) -> CheckResult:
        order.append((progress.calls[-1][0], gen.category))
        assert set(ctx.results) >= {"is_safe#ex1", "hello#session1"}   # every result is available to evaluation
        return fake_evaluate_function(gen, res, ctx)

    world = make_world(evaluate_function=spy)
    analyze(world, subject, path_project(store, source), store, tmp_path, progress=progress)
    assert ("explicit", "explicit_tests") in order and ("derived", "derived_tests") in order
    assert all(stage == "explicit" for stage, cat in order if cat == "explicit_tests")
    assert all(stage == "derived" for stage, cat in order if cat == "derived_tests")


def test_path_projects_are_resnapshotted_on_each_analysis(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    world = make_world()
    project = path_project(store, source)
    analyze(world, subject, project, store, tmp_path)
    first_root = world.sandbox.calls[-1][1]
    assert "<= limit" in world.sandbox.seen_sources["is_safe#ex1"]

    (source / "pkg" / "safe_speed.py").write_text("def is_safe(speed, limit):\n    return speed < limit\n", encoding="utf-8")
    (source / "pkg" / "absent.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    report = analyze(world, subject, store.get_project("proj"), store, tmp_path)
    second_root = world.sandbox.calls[-1][1]

    assert second_root != first_root
    assert "< limit" in world.sandbox.seen_sources["is_safe#ex1"]          # the student's latest edit
    assert by_id(report)["structure:file:pkg/absent.py"].status == "pass"
    saved = store.get_project("proj")
    assert Path(saved.snapshot_path) == second_root
    assert saved.python_files == 3
    assert saved.source_path == str(source)                              # the user's folder is never analyzed in place

    for _ in range(4):
        analyze(world, subject, store.get_project("proj"), store, tmp_path)
    assert len(list((tmp_path / "snapshots" / "proj").iterdir())) <= 3    # old snapshots are pruned


def test_zip_projects_reuse_their_snapshot(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    snapshot = tmp_path / "data" / "snap"
    shutil.copytree(source, snapshot)
    project = ProjectRecord(id="proj", name="z", source_kind="zip", snapshot_path=str(snapshot), file_count=4, python_files=2)
    store.save_project(project)
    world = make_world()
    report = analyze(world, subject, project, store, tmp_path)
    assert world.sandbox.calls[0][1] == snapshot
    assert store.get_project("proj") == project
    assert report.project.file_count == 4
    assert not (tmp_path / "snapshots" / "proj").exists()


def test_missing_source_folder_falls_back_to_last_snapshot(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    snapshot = tmp_path / "data" / "snap"
    shutil.copytree(source, snapshot)
    project = ProjectRecord(id="proj", name="p", source_kind="path", source_path=str(tmp_path / "gone"), snapshot_path=str(snapshot))
    store.save_project(project)
    report = analyze(make_world(), subject, project, store, tmp_path)
    assert any("no longer available" in w for w in report.pipeline_warnings)

    lost = project.model_copy(update={"snapshot_path": str(tmp_path / "nothing")})
    with pytest.raises(AnalysisError, match="snapshot is missing"):
        analyze(make_world(), subject, lost, store, tmp_path)


def test_no_sandbox_fails_before_running_anything(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    world = make_world()
    with pytest.raises(AnalysisError) as err:
        analyze(world, subject, path_project(store, source), store, tmp_path, settings=Settings())
    assert str(err.value) == NO_DOCKER_MESSAGE
    assert world.sandbox.calls == [] and world.factory.requested == []
    assert store.list_analyses() == []


def test_docker_is_used_when_ready(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    world = make_world(docker=FakeDockerStatus(available=True, image_ready=True, error=None, image="img:1"))
    report = analyze(world, subject, path_project(store, source), store, tmp_path,
                     settings=Settings(docker_image="img:1"))
    assert world.factory.requested == [("docker", "img:1")]
    assert report.sandbox.mode == "docker"
    assert report.pipeline_warnings == []


def test_auto_falls_back_to_acknowledged_local_mode_with_a_warning(
    store: Store, subject: SubjectRecord, source: Path, tmp_path: Path
) -> None:
    world = make_world()
    report = analyze(world, subject, path_project(store, source), store, tmp_path,
                     settings=Settings(sandbox_mode="auto", local_mode_acknowledged=True))
    assert world.factory.requested[0][0] == "local"
    assert any("Developer mode" in w for w in report.pipeline_warnings)


def test_check_files_are_spec_paths_and_locations_actual_paths(
    store: Store, subject: SubjectRecord, source: Path, tmp_path: Path
) -> None:
    (source / "misplaced").mkdir()
    shutil.move(source / "pkg" / "hello.py", source / "misplaced" / "hello.py")
    world = make_world()
    report = analyze(world, subject, path_project(store, source), store, tmp_path)
    checks = by_id(report)

    syntax = checks["syntax:pkg/hello.py"]
    assert syntax.file == "pkg/hello.py"                       # stable across runs
    assert syntax.location is not None and syntax.location.file == "misplaced/hello.py"
    assert checks["structure:file:pkg/hello.py"].diagnosis == "misplaced_file"
    # the misplaced script still runs, on the file actually found
    jobs = {j.id: j for j in world.sandbox.calls[0][0].jobs}
    assert jobs["hello#session1"].script_path == "misplaced/hello.py"
    assert checks["test:hello#session1"].status == "pass"


def test_syntax_error_and_missing_function_block_tests(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    (source / "pkg" / "hello.py").write_text("if True\n    print('x')\n", encoding="utf-8")
    (source / "pkg" / "safe_speed.py").write_text("def is_save(speed, limit):\n    return True\n", encoding="utf-8")
    world = make_world()
    checks = by_id(analyze(world, subject, path_project(store, source), store, tmp_path))
    assert checks["syntax:pkg/hello.py"].status == "fail"
    assert checks["test:hello#session1"].status == "skipped"
    assert checks["test:hello#session1"].blocked_by == "syntax:pkg/hello.py"
    for test_id in ("is_safe#ex1", "is_safe#ex2", "is_safe#derived1"):
        assert checks[f"test:{test_id}"].status == "skipped"
        assert checks[f"test:{test_id}"].blocked_by == "function:safe_speed:is_safe"
    assert {j.id for j in world.sandbox.calls[0][0].jobs} == {"import:safe_speed"}


def test_sandbox_failures(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    world = make_world()
    world.sandbox.error = RuntimeError("container died")
    with pytest.raises(AnalysisError, match="container died"):
        analyze(world, subject, path_project(store, source), store, tmp_path)

    world = make_world()
    world.sandbox.drop = {"is_safe#ex2"}
    report = analyze(world, subject, store.get_project("proj"), store, tmp_path)
    assert by_id(report)["test:is_safe#ex2"].status == "skipped"
    assert any("no result for 1 job" in w and "is_safe#ex2" in w for w in report.pipeline_warnings)


def test_fix_suggestions_are_best_effort(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    report = analyze(make_world(fixes_error=ValueError("bad hunk")), subject, path_project(store, source), store, tmp_path)
    assert any("Fix suggestions could not be computed: bad hunk" in w for w in report.pipeline_warnings)
    assert store.get_analysis(report.id) is not None


def test_check_producer_failure_aborts_the_analysis(store: Store, subject: SubjectRecord, source: Path, tmp_path: Path) -> None:
    def broken(*_: Any) -> list[CheckResult]:
        raise RuntimeError("constraints exploded")

    with pytest.raises(RuntimeError, match="constraints exploded"):
        analyze(make_world(check_constraints=broken), subject, path_project(store, source), store, tmp_path)
    assert store.list_analyses() == []


def check(id: str, status: str, file: str | None = None) -> CheckResult:
    return CheckResult(id=id, category="structure", status=status, title=id, message="m", file=file)  # type: ignore[arg-type]


def test_normalize_check_files() -> None:
    file_map = {"a/x.py": "root/elsewhere/x.py", "a/y.py": "root/a/y.py", "a/z.py": None, "a/w.py": "a/w.py"}
    checks = [check("1", "pass", "root/elsewhere/x.py"), check("2", "pass", "a/y.py"), check("3", "pass", "root/a/y.py"),
              check("4", "pass", "other.py"), check("5", "pass", None), check("6", "pass", "a/w.py")]
    out = normalize_check_files(checks, file_map)
    assert [c.file for c in out] == ["a/x.py", "a/y.py", "a/y.py", "other.py", None, "a/w.py"]


def test_dedupe_checks_keeps_the_worst_status_in_first_position() -> None:
    checks = [check("a", "pass"), check("b", "fail"), check("a", "fail"), check("b", "pass"), check("a", "warning")]
    out = dedupe_checks(checks)
    assert [(c.id, c.status) for c in out] == [("a", "fail"), ("b", "fail")]
