"""End-to-end: the real pipeline (local sandbox) on ``demo/subject_demo.html`` against the demo projects
and the fixture variants, judged by ``backend/tests/fixtures/expected.json`` (docs/DEMO_EXPECTATIONS.md).

The whole module is skipped while a pipeline module is not written yet. A module that exists but
fails to import is reported as an error, never silently skipped.
"""
from __future__ import annotations

import importlib.util
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from conftest import DEMO_DIR, FIXTURES_DIR, REPO

REQUIRED_MODULES = (
    "premoulinette.subject.pipeline",
    "premoulinette.project.ingest",
    "premoulinette.project.tree",
    "premoulinette.project.root_detect",
    "premoulinette.project.git_info",
    "premoulinette.languages.python.static",
    "premoulinette.languages.python.checks_structure",
    "premoulinette.languages.python.checks_static",
    "premoulinette.testgen.generate",
    "premoulinette.sandbox.base",
    "premoulinette.sandbox.detect",
    "premoulinette.sandbox.local",
    "premoulinette.compare.evaluate",
    "premoulinette.explain.fixes",
    "premoulinette.explain.templates",
    "premoulinette.scoring.score",
    "premoulinette.report.export",
)
ORACLE_FILE = FIXTURES_DIR / "expected.json"
SUBJECT_FILE = DEMO_DIR / "subject_demo.html"


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


_missing = [m for m in REQUIRED_MODULES if not _module_exists(m)]
if _missing:
    pytest.skip(f"pipeline modules not written yet: {', '.join(_missing)}", allow_module_level=True)
if not ORACLE_FILE.is_file() or not SUBJECT_FILE.is_file():
    pytest.skip("demo subject or expected.json missing", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from premoulinette.api.app import create_app  # noqa: E402
from premoulinette.api.subject_records import record_from_parse  # noqa: E402
from premoulinette.engine.pipeline import run_analysis  # noqa: E402
from premoulinette.results.models import AnalysisReport, CheckResult  # noqa: E402
from premoulinette.store.db import ProjectRecord, Settings, Store, SubjectRecord  # noqa: E402
from premoulinette.subject.pipeline import parse_subject  # noqa: E402

LOCAL = Settings(sandbox_mode="local", local_mode_acknowledged=True)
ORACLE: dict[str, Any] = json.loads(ORACLE_FILE.read_text(encoding="utf-8"))


def _cases() -> dict[str, dict[str, Any]]:
    cases = dict(ORACLE["variants"])
    for name, entry in ORACLE["demo_projects"].items():
        base = ORACLE["variants"][entry["same_as_variant"]] if "same_as_variant" in entry else {}
        cases[name] = {**base, **entry}
    return {name: c for name, c in cases.items() if (REPO / c["path"]).is_dir()}


CASES = _cases()
NAMES = sorted(CASES)


# ---- shared analysis runs ---------------------------------------------------------------------------


@dataclass
class E2E:
    store: Store
    subject: SubjectRecord
    snapshots: Path
    reports: dict[str, AnalysisReport] = field(default_factory=dict)

    def report(self, name: str) -> AnalysisReport:
        """Analyze a case once per test session (the source folder is snapshotted, never modified)."""
        if name not in self.reports:
            src = (REPO / CASES[name]["path"]).resolve()
            project = ProjectRecord(id=name, name=name, source_kind="path", source_path=str(src), snapshot_path=str(src))
            self.store.save_project(project)
            self.reports[name] = run_analysis(
                self.subject, project, LOCAL, self.store, lambda stage, fraction: None, snapshots_dir=self.snapshots
            )
        return self.reports[name]


@pytest.fixture(scope="module")
def e2e(tmp_path_factory: pytest.TempPathFactory) -> Iterator[E2E]:
    data = tmp_path_factory.mktemp("e2e-data")
    store = Store(data / "premoulinette.db")
    doc, parsed = parse_subject(SUBJECT_FILE.read_bytes(), SUBJECT_FILE.name)
    subject = record_from_parse("demo-subject", SUBJECT_FILE.name, doc, parsed, SUBJECT_FILE)
    store.save_subject(subject)
    yield E2E(store=store, subject=subject, snapshots=data / "snapshots")
    store.close()


# ---- oracle helpers -----------------------------------------------------------------------------------


def _accepts(expected: Any, actual: Any) -> bool:
    if expected is None:
        return True
    return actual in expected if isinstance(expected, list) else actual == expected


def _matches(check: CheckResult, entry: dict[str, Any]) -> bool:
    if not _accepts(entry.get("status"), check.status):
        return False
    if "diagnosis" in entry and not _accepts(entry["diagnosis"], check.diagnosis):
        return False
    if "severity" in entry and not _accepts(entry["severity"], check.severity):
        return False
    if "line" in entry and (check.location is None or check.location.line != entry["line"]):
        return False
    return True


def _describe(checks: list[CheckResult]) -> str:
    if not checks:
        return "  (no check with this prefix)"
    return "\n".join(
        f"  {c.id}: status={c.status} diagnosis={c.diagnosis} severity={c.severity} "
        f"line={c.location.line if c.location else None} blocked_by={c.blocked_by} :: {c.message}"
        for c in checks
    )


def _with_prefix(report: AnalysisReport, prefix: str) -> list[CheckResult]:
    return [c for c in report.checks if c.id.startswith(prefix)]


# ---- oracle tests ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_verdict_and_scores(e2e: E2E, name: str) -> None:
    case, report = CASES[name], e2e.report(name)
    score = report.score
    failing = [c for c in report.checks if c.mandatory and c.status in ("fail", "skipped")]
    assert score.verdict == case["verdict"], f"{name}: mandatory failures:\n{_describe(failing)}"
    if "mandatory_readiness" in case:
        assert score.mandatory_readiness == pytest.approx(case["mandatory_readiness"]), _describe(failing)
    if "bonus_completion" in case:
        assert score.bonus_completion == pytest.approx(case["bonus_completion"])
    assert report.sandbox.mode == "local"


@pytest.mark.parametrize("name", NAMES)
def test_required_detections(e2e: E2E, name: str) -> None:
    report = e2e.report(name)
    problems = []
    for entry in CASES[name]["detections"]:
        candidates = _with_prefix(report, entry["id_prefix"])
        hits = [c for c in candidates if _matches(c, entry)]
        if len(hits) < entry.get("min_count", 1):
            problems.append(f"{entry}\n{_describe(candidates)}")
    assert not problems, f"{name}: missing detections:\n" + "\n".join(problems)


@pytest.mark.parametrize("name", NAMES)
def test_isolated_mutation_must_pass(e2e: E2E, name: str) -> None:
    report = e2e.report(name)
    problems = []
    for prefix in CASES[name]["must_pass"]:
        candidates = _with_prefix(report, prefix)
        if not candidates or any(c.status != "pass" for c in candidates):
            problems.append(f"{prefix}\n{_describe(candidates)}")
    assert not problems, f"{name}: checks that must pass:\n" + "\n".join(problems)


@pytest.mark.parametrize("name", [n for n in NAMES if CASES[n].get("exhaustive")])
def test_no_unexpected_mandatory_failure(e2e: E2E, name: str) -> None:
    case, report = CASES[name], e2e.report(name)
    allowed = [d["id_prefix"] for d in case["detections"]] + list(case["tolerated"])
    unexpected = [
        c for c in report.checks
        if c.mandatory and c.status in ("fail", "skipped") and not any(c.id.startswith(p) for p in allowed)
    ]
    assert not unexpected, f"{name}: unexpected mandatory failures:\n{_describe(unexpected)}"


# ---- engine-specific guarantees -----------------------------------------------------------------------------


def test_misplaced_file_checks_use_spec_paths(e2e: E2E) -> None:
    if "mysteryinc_buggy" not in CASES:
        pytest.skip("buggy demo project missing")
    report = e2e.report("mysteryinc_buggy")
    spec_path = "MysteryInc/FirstLaunch/route_math/mission_clock.py"
    actual_path = "MysteryInc/FirstLaunch/mission_clock.py"
    for c in report.checks:
        if c.exercise_id == "mission_clock" or c.id.startswith(("returns:mission_clock", "test:mission_clock")):
            assert c.file == spec_path, c
        elif c.file == actual_path:
            # only checks about the stray file itself may name it (e.g. structure:extra:<path>)
            assert c.id.endswith(actual_path), c
    located = [c for c in _with_prefix(report, "test:mission_clock#ex") if c.location is not None]
    assert located and all(c.location.file == actual_path for c in located)


def test_reanalysis_is_numbered_and_comparable(e2e: E2E) -> None:
    if "mysteryinc_fixed" not in CASES:
        pytest.skip("fixed demo project missing")
    first = e2e.report("mysteryinc_fixed")
    project = e2e.store.get_project("mysteryinc_fixed")
    second = run_analysis(e2e.subject, project, LOCAL, e2e.store, lambda s, f: None, snapshots_dir=e2e.snapshots)
    assert second.number == first.number + 1
    assert {c.id for c in second.checks} == {c.id for c in first.checks}     # stable ids across runs
    comparison = e2e.store.compare(first.id, second.id)
    assert comparison.fixed == [] and comparison.new_failures == []


# ---- through the HTTP API ------------------------------------------------------------------------------------


def test_demo_flow_through_the_api(tmp_path: Path) -> None:
    if not (DEMO_DIR / "projects" / "mysteryinc_buggy").is_dir():
        pytest.skip("buggy demo project missing")
    app = create_app(tmp_path / "data", frontend_dist=tmp_path / "no-dist")
    with TestClient(app, base_url="http://127.0.0.1:8765", headers={"X-PreMoulinette": "1"}) as client:
        assert client.put("/api/settings", json={"sandbox_mode": "local", "local_mode_acknowledged": True}).status_code == 200
        demo = client.post("/api/demo/load", json={"variant": "buggy"}).json()
        assert demo["subject"]["title"] == "TP 1 — MysteryInc: First Launch"
        job = client.post("/api/analyses", json={"subject_id": demo["subject"]["id"], "project_id": demo["project"]["id"]})
        assert job.status_code == 200, job.text
        state = _wait(client, job.json()["job_id"])
        assert state["status"] == "done", state
        report = client.get(f"/api/analyses/{state['result_id']}").json()
        assert report["score"]["verdict"] == "not_ready"

        # the file viewer serves the analyzed snapshot
        f = client.get("/api/projects/demo-buggy/file", params={"path": "MysteryInc/FirstLaunch/launch_sequence.py"})
        assert f.status_code == 200 and "callect" in f.json()["content"]

        export = client.get(f"/api/analyses/{state['result_id']}/export", params={"format": "md"})
        assert export.status_code == 200
        assert export.headers["content-disposition"] == 'attachment; filename="premoulinette-report-1.md"'

        check_id = "test:is_safe#ex1"
        explained = client.post(f"/api/analyses/{state['result_id']}/checks/{quote(check_id, safe='')}/explain",
                                json={"mode": "explain", "provider": "template", "lang": "en"})
        assert explained.status_code == 200, explained.text
        assert explained.json()["provider"] == "template"


def _wait(client: TestClient, job_id: str, timeout: float = 180.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["status"] in ("done", "error"):
            return state
        assert time.monotonic() < deadline, state
        time.sleep(0.1)
