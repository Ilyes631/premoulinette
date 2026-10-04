from __future__ import annotations

from pathlib import Path

import pytest

from test_api_fakes import harness_factory  # noqa: F401  (fixture)


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>SPA</title>", encoding="utf-8")
    (d / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("NOPE", encoding="utf-8")
    return d


def test_spa_index_and_client_routes(harness_factory, dist: Path) -> None:
    h = harness_factory(frontend_dist=dist)
    for path in ("/", "/analyses/123", "/settings"):
        r = h.client.get(path)
        assert r.status_code == 200, path
        assert "<title>SPA</title>" in r.text
    asset = h.client.get("/assets/app.js")
    assert asset.status_code == 200 and asset.text == "console.log(1)"


def test_spa_never_shadows_api(harness_factory, dist: Path) -> None:
    h = harness_factory(frontend_dist=dist)
    assert h.client.get("/api/health").json()["ok"] is True
    missing = h.client.get("/api/nope")
    assert missing.status_code == 404
    assert "SPA" not in missing.text


def test_spa_missing_asset_and_traversal(harness_factory, dist: Path) -> None:
    h = harness_factory(frontend_dist=dist)
    assert h.client.get("/assets/missing.js").status_code == 404
    r = h.client.get("/..%2Foutside.txt")
    assert "NOPE" not in r.text


def test_no_dist_means_api_only(harness_factory, tmp_path: Path) -> None:
    h = harness_factory(frontend_dist=tmp_path / "missing")
    assert h.client.get("/").status_code == 404
