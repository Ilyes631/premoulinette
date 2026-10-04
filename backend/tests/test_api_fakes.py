"""Shared fakes for the API/engine unit tests (this module contains no tests).

Only documented contracts are mimicked: modules owned by other engineers are never imported here,
so these tests stay independent from their progress. The store is the real one (sqlite in tmp).
"""
from __future__ import annotations

import io
import os
import shutil
import zipfile
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from premoulinette.api.app import create_app
from premoulinette.api.context import AppContext
from premoulinette.api.services import ApiServices
from premoulinette.engine.jobs import JobManager
from premoulinette.results.models import (
    AnalysisReport,
    CheckResult,
    GitInfo,
    ProjectSummary,
    SandboxInfo,
    ScoreSummary,
    SubjectSummary,
    TreeEntry,
)
from premoulinette.spec.models import (
    ExerciseSpec,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    Param,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
    SpecMetadata,
)
from premoulinette.store.db import Store

BASE_URL = "http://127.0.0.1:8765"
CSRF = {"X-PreMoulinette": "1"}


# ---- spec / generated tests -----------------------------------------------------------------------


def make_spec(title: str = "Fake TP") -> PracticalSpec:
    """safe_speed (2 explicit tests), hello (script, 1 session), absent (1 test, file usually missing)."""
    return PracticalSpec(
        metadata=SpecMetadata(title=title),
        exercises=[
            ExerciseSpec(
                id="safe_speed", title="Safe speed", file_path="pkg/safe_speed.py",
                functions=[FunctionSpec(
                    signature=FunctionSignature(name="is_safe", params=[Param(name="speed"), Param(name="limit")]),
                    tests=[
                        FunctionTest(id="is_safe#ex1", function="is_safe", args=["200", "250"], expected_return="True"),
                        FunctionTest(id="is_safe#ex2", function="is_safe", args=["300", "250"], expected_return="False"),
                    ],
                )],
            ),
            ExerciseSpec(
                id="hello", title="Hello", kind="script", file_path="pkg/hello.py",
                script=ScriptSpec(tests=[ScriptTest(id="hello#session1", stdin="Bob\n", expected_stdout="Hi Bob\n")]),
            ),
            ExerciseSpec(
                id="absent", title="Absent", file_path="pkg/absent.py",
                functions=[FunctionSpec(
                    signature=FunctionSignature(name="f"),
                    tests=[FunctionTest(id="f#ex1", function="f", expected_return="1")],
                )],
            ),
        ],
    )


class FakeGeneratedFunctionTest(BaseModel):
    test: FunctionTest
    exercise_id: str
    category: Literal["explicit_tests", "derived_tests", "heuristic_tests"]
    rule: str | None = None


class FakeGeneratedScriptTest(BaseModel):
    test: ScriptTest
    exercise_id: str
    category: Literal["explicit_tests", "output"] = "output"


def fake_generate_tests(spec: PracticalSpec) -> tuple[list[FakeGeneratedFunctionTest], list[FakeGeneratedScriptTest]]:
    fn = [FakeGeneratedFunctionTest(test=t, exercise_id=e.id, category="explicit_tests") for e, _, t in spec.all_function_tests()]
    first = next(((e, f) for e in spec.exercises for f in e.functions), None)
    if first is not None:
        e, f = first
        fn.append(FakeGeneratedFunctionTest(
            test=FunctionTest(id=f"{f.name}#derived1", function=f.name, args=["250", "250"], expected_return="True"),
            exercise_id=e.id, category="derived_tests", rule="speed <= limit",
        ))
    scripts = [FakeGeneratedScriptTest(test=t, exercise_id=e.id) for e, t in spec.all_script_tests()]
    return fn, scripts


# ---- subject parsing --------------------------------------------------------------------------------


class ParseRecorder:
    """Fake ``parse_subject`` recording its calls."""

    def __init__(self, spec_factory: Any = make_spec, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.spec_factory = spec_factory
        self.error = error

    def __call__(self, data: bytes, filename: str, *, use_ai: bool = False, api_key: str | None = None) -> tuple[Any, Any]:
        self.calls.append({"filename": filename, "use_ai": use_ai, "api_key": api_key, "size": len(data)})
        if self.error is not None:
            raise self.error
        text = data.decode("utf-8", errors="replace")
        doc = SimpleNamespace(
            source_name=filename, media_type="html", title="Doc title", text=text, blocks=[],
            sha256="0" * 64, warnings=["doc warning"],
        )
        return doc, SimpleNamespace(spec=self.spec_factory(), warnings=["parse warning"], stats={})


# ---- project ingestion ------------------------------------------------------------------------------


def _snapshot(dest: Path, kind: str, name: str, source: str | None) -> SimpleNamespace:
    files = [p for p in dest.rglob("*") if p.is_file()]
    return SimpleNamespace(
        root=dest, source_kind=kind, source_path=source, name=name, file_count=len(files),
        total_bytes=sum(p.stat().st_size for p in files), skipped=[], warnings=[],
    )


def fake_snapshot_from_path(src: Path, dest: Path, *, kind: str = "path") -> SimpleNamespace:
    shutil.copytree(src, dest)
    return _snapshot(dest, kind, Path(src).name, str(src))


def fake_snapshot_from_zip(data: bytes, dest: Path, name: str) -> SimpleNamespace:
    dest.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            target = (dest / info.filename).resolve()
            assert target.is_relative_to(dest.resolve())
            if not info.is_dir():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info))
    return _snapshot(dest, "zip", name, None)


def fake_snapshot_from_upload(files: list[tuple[str, bytes]], dest: Path, name: str) -> SimpleNamespace:
    dest.mkdir(parents=True)
    for rel, data in files:
        target = (dest / rel).resolve()
        assert target.is_relative_to(dest.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return _snapshot(dest, "upload", name, None)


def fake_list_tree(root: Path) -> list[TreeEntry]:
    entries: list[TreeEntry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        base = Path(dirpath)
        for d in dirnames:
            entries.append(TreeEntry(path=(base / d).relative_to(root).as_posix(), kind="directory"))
        for f in sorted(filenames):
            p = base / f
            entries.append(TreeEntry(path=p.relative_to(root).as_posix(), kind="file", size=p.stat().st_size))
    return sorted(entries, key=lambda e: e.path)


def fake_read_git_info(repo_root: Path, required_paths: list[str]) -> GitInfo:
    return GitInfo(is_repo=True, branch="main", head="abc1234", untracked=["new.py"])


class FakeDockerStatus(BaseModel):
    available: bool = False
    version: str | None = None
    image: str = "python:3.12-slim"
    image_ready: bool = False
    error: str | None = "docker: command not found"


# ---- reports ----------------------------------------------------------------------------------------


def make_score(verdict: Literal["ready", "not_ready"] = "not_ready") -> ScoreSummary:
    return ScoreSummary(
        readiness=50.0, mandatory_readiness=50.0, mandatory_passed=1, mandatory_total=2,
        mandatory_failures=0 if verdict == "ready" else 1, bonus_completion=None, bonus_passed=0, bonus_total=0,
        confidence="high", verdict=verdict,
        verdict_title="READY TO SUBMIT" if verdict == "ready" else "DO NOT SUBMIT YET", verdict_message="msg",
    )


def make_report(
    subject_id: str, project_id: str, *, number: int = 1, checks: list[CheckResult] | None = None,
    report_id: str | None = None,
) -> AnalysisReport:
    return AnalysisReport(
        id=report_id or f"rep-{subject_id}-{project_id}-{number}",
        number=number,
        subject=SubjectSummary(id=subject_id, title="Fake TP", language="python", parser="heuristic"),
        project=ProjectSummary(id=project_id, name="proj", source_kind="path"),
        sandbox=SandboxInfo(mode="local"),
        spec=make_spec(),
        checks=checks if checks is not None else [
            CheckResult(id="test:is_safe#ex1", category="explicit_tests", status="fail", severity="major",
                        title="Wrong return type", message="m", diagnosis="str_instead_of_bool",
                        file="pkg/safe_speed.py"),
            CheckResult(id="structure:file:pkg/hello.py", category="structure", status="pass", title="ok", message="m"),
        ],
        score=make_score(),
    )


# ---- app fixtures -------------------------------------------------------------------------------------


def make_services(**overrides: Any) -> ApiServices:
    base = ApiServices(
        parse_subject=ParseRecorder(),
        validate_spec=lambda spec: [],
        generate_tests=fake_generate_tests,
        snapshot_from_path=fake_snapshot_from_path,
        snapshot_from_zip=fake_snapshot_from_zip,
        snapshot_from_upload=fake_snapshot_from_upload,
        list_tree=fake_list_tree,
        read_git_info=fake_read_git_info,
        detect_docker=lambda image="python:3.12-slim", timeout=4.0: FakeDockerStatus(image=image),
        pull_image=lambda image: (True, "pulled"),
    )
    return replace(base, **overrides)


class AppHarness:
    """A TestClient bound to an app built on a temporary data dir."""

    def __init__(self, tmp_path: Path, services: ApiServices | None = None, **app_kwargs: Any) -> None:
        self.data_dir = tmp_path / "data"
        self.store = Store(tmp_path / "test.db")
        self.jobs = JobManager(max_workers=2)
        self.app = create_app(
            self.data_dir, self.store, services=services or make_services(), jobs=self.jobs,
            frontend_dist=app_kwargs.pop("frontend_dist", tmp_path / "no-dist"), **app_kwargs,
        )
        self.client = TestClient(self.app, base_url=BASE_URL, headers=CSRF)
        self.bare = TestClient(self.app, base_url=BASE_URL)   # no CSRF header

    @property
    def ctx(self) -> AppContext:
        return self.app.state.ctx

    def close(self) -> None:
        self.jobs.shutdown(wait=True)
        self.store.close()


@pytest.fixture
def harness_factory(tmp_path: Path) -> Iterator[Any]:
    made: list[AppHarness] = []

    def make(services: ApiServices | None = None, **kwargs: Any) -> AppHarness:
        h = AppHarness(tmp_path, services, **kwargs)
        made.append(h)
        return h

    yield make
    for h in made:
        h.close()


def make_project_dir(root: Path) -> Path:
    """A small student project: pkg/safe_speed.py, pkg/hello.py, README.md, a binary file."""
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "safe_speed.py").write_text("def is_safe(speed, limit):\n    return speed <= limit\n", encoding="utf-8")
    (root / "pkg" / "hello.py").write_text("name = input()\nprint('Hi', name)\n", encoding="utf-8")
    (root / "README.md").write_text("# readme\n", encoding="utf-8")
    (root / "data.bin").write_bytes(b"\x00\x01\x02")
    return root
