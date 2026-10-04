from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from premoulinette.api.services import ApiServices
from test_api_fakes import ParseRecorder, harness_factory, make_project_dir, make_services  # noqa: F401
from conftest import DEMO_DIR


@pytest.fixture
def demo_dir(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    (root / "subject_demo.html").write_text("<h1>Demo</h1>", encoding="utf-8")
    make_project_dir(root / "projects" / "mysteryinc_buggy")
    make_project_dir(root / "projects" / "mysteryinc_fixed")
    return root


def test_demo_load_creates_records_without_copying(harness_factory, demo_dir: Path) -> None:
    parser = ParseRecorder()
    h = harness_factory(make_services(parse_subject=parser), demo_dir=demo_dir)
    r = h.client.post("/api/demo/load", json={"variant": "buggy"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["subject"]["id"] == "demo-subject"
    assert data["subject"]["source_name"] == "subject_demo.html"
    project = data["project"]
    assert project["id"] == "demo-buggy"
    assert project["source_kind"] == "demo"
    assert project["source_path"] == str((demo_dir / "projects" / "mysteryinc_buggy").resolve())
    assert project["python_files"] == 2
    assert "pkg/safe_speed.py" in {e["path"] for e in project["tree"]}

    rec = h.store.get_project("demo-buggy")
    assert rec.snapshot_path == project["source_path"]
    assert h.store.get_subject("demo-subject").raw_path == str((demo_dir / "subject_demo.html").resolve())
    assert list(h.ctx.paths.snapshots.iterdir()) == []      # nothing copied
    assert list(h.ctx.paths.subjects.iterdir()) == []

    # the file viewer works on the demo project
    f = h.client.get("/api/projects/demo-buggy/file", params={"path": "pkg/hello.py"})
    assert f.status_code == 200

    # reloading keeps the subject (and its edits); the other variant is another project
    fixed = h.client.post("/api/demo/load", json={"variant": "fixed"}).json()
    assert fixed["project"]["id"] == "demo-fixed"
    assert fixed["subject"]["id"] == "demo-subject"
    assert len(parser.calls) == 1
    h.client.post("/api/demo/load", json={"variant": "buggy", "reset": True})
    assert len(parser.calls) == 2
    assert len(h.store.list_projects()) == 2


def test_demo_default_variant_and_validation(harness_factory, demo_dir: Path) -> None:
    h = harness_factory(demo_dir=demo_dir)
    assert h.client.post("/api/demo/load").json()["project"]["id"] == "demo-buggy"
    assert h.client.post("/api/demo/load", json={"variant": "evil/../x"}).status_code == 422


def test_demo_missing_files(harness_factory, tmp_path: Path) -> None:
    h = harness_factory(demo_dir=tmp_path / "nowhere")
    assert h.client.post("/api/demo/load", json={"variant": "buggy"}).status_code == 404


def test_demo_load_with_real_parser(harness_factory) -> None:
    """Runs only once the subject parser and the tree module exist (integration)."""
    for module in ("premoulinette.subject.pipeline", "premoulinette.project.tree"):
        if importlib.util.find_spec(module) is None:
            pytest.skip(f"{module} is not available yet")
    if not (DEMO_DIR / "projects" / "mysteryinc_buggy").is_dir():
        pytest.skip("demo project missing")
    real = ApiServices()
    h = harness_factory(make_services(parse_subject=real.parse_subject, list_tree=real.list_tree), demo_dir=DEMO_DIR)
    r = h.client.post("/api/demo/load", json={"variant": "buggy"})
    assert r.status_code == 200, r.text
    subject = r.json()["subject"]
    assert subject["title"] == "TP 1 — MysteryInc: First Launch"
    assert subject["stats"]["exercises"] == 11
    assert subject["stats"]["bonus_exercises"] == 3
