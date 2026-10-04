from __future__ import annotations

from pathlib import Path

import pytest

from premoulinette.spec.models import PracticalSpec
from test_api_fakes import ParseRecorder, harness_factory, make_services  # noqa: F401  (fixture)

HTML = b"<html><head><title>Fake TP</title></head><body><h1>Fake TP</h1></body></html>"


def upload(h, name: str = "subject.html", data: bytes = HTML):
    return h.client.post("/api/subjects", files={"file": (name, data, "text/html")})


def test_upload_parses_and_stores(harness_factory) -> None:
    parser = ParseRecorder()
    h = harness_factory(make_services(parse_subject=parser))
    r = upload(h)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["title"] == "Fake TP"
    assert view["source_name"] == "subject.html"
    assert view["media_type"] == "html"
    assert view["parser"] == "heuristic"
    assert view["stats"]["exercises"] == 3
    assert view["warnings"] == ["doc warning", "parse warning"]
    assert view["validation"] == []
    assert view["spec"]["metadata"]["source_name"] == "subject.html"
    assert view["spec"]["metadata"]["source_sha256"] == "0" * 64
    assert parser.calls == [{"filename": "subject.html", "use_ai": False, "api_key": None, "size": len(HTML)}]

    rec = h.store.get_subject(view["id"])
    assert rec is not None and rec.raw_path is not None
    raw = Path(rec.raw_path)
    assert raw.read_bytes() == HTML
    assert raw.parent == h.ctx.paths.subjects / view["id"]

    assert [s["id"] for s in h.client.get("/api/subjects").json()] == [view["id"]]
    assert h.client.get(f"/api/subjects/{view['id']}").json()["id"] == view["id"]
    doc = h.client.get(f"/api/subjects/{view['id']}/document").json()
    assert doc == {"text": HTML.decode(), "html": None, "media_type": "html"}


def test_hostile_filename_is_sanitized(harness_factory) -> None:
    h = harness_factory()
    r = upload(h, name="..\\..\\evil name?.md")
    assert r.status_code == 200
    raw = Path(h.store.get_subject(r.json()["id"]).raw_path)
    assert raw.parent == h.ctx.paths.subjects / r.json()["id"]
    assert raw.name == "evil_name_.md"


def test_unsupported_extension(harness_factory) -> None:
    h = harness_factory()
    r = upload(h, name="subject.exe")
    assert r.status_code == 415
    assert h.client.get("/api/subjects").json() == []


def test_missing_file_field(harness_factory) -> None:
    h = harness_factory()
    r = h.client.post("/api/subjects", data={"other": "x"})
    assert r.status_code == 400


def test_too_large_subject(harness_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    import premoulinette.api.routes_subjects as routes

    monkeypatch.setattr(routes, "SUBJECT_MAX_BYTES", 10)
    h = harness_factory()
    r = upload(h, data=b"x" * 11)
    assert r.status_code == 413


def test_unreadable_document_is_400(harness_factory) -> None:
    h = harness_factory(make_services(parse_subject=ParseRecorder(error=ValueError("corrupt PDF"))))
    r = upload(h, name="subject.pdf", data=b"%PDF-broken")
    assert r.status_code == 400
    assert "corrupt PDF" in r.json()["detail"]


def test_put_spec_marks_reviewed_and_renames(harness_factory) -> None:
    h = harness_factory()
    view = upload(h).json()
    spec = view["spec"]
    spec["metadata"]["title"] = "Edited title"
    spec["exercises"][0]["title"] = "Edited exercise"
    r = h.client.put(f"/api/subjects/{view['id']}/spec", json=spec)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["title"] == "Edited title"
    assert out["spec"]["metadata"]["reviewed_by_user"] is True
    assert out["spec"]["exercises"][0]["title"] == "Edited exercise"
    assert h.store.get_subject(view["id"]).spec.metadata.reviewed_by_user is True


def test_put_invalid_spec_is_422_with_loc_and_msg(harness_factory) -> None:
    h = harness_factory()
    view = upload(h).json()
    spec = view["spec"]
    spec["exercises"][1]["id"] = spec["exercises"][0]["id"]   # duplicate exercise id
    r = h.client.put(f"/api/subjects/{view['id']}/spec", json=spec)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail and all({"loc", "msg"} <= set(d) for d in detail)
    assert "Duplicate exercise ids" in " ".join(d["msg"] for d in detail)

    bad_type = h.client.put(f"/api/subjects/{view['id']}/spec", json={"exercises": "nope"})
    assert bad_type.status_code == 422
    assert any("exercises" in [str(x) for x in d["loc"]] for d in bad_type.json()["detail"])


def test_tests_endpoint_groups_by_category(harness_factory) -> None:
    h = harness_factory()
    view = upload(h).json()
    groups = h.client.get(f"/api/subjects/{view['id']}/tests").json()
    assert [g["test"]["id"] for g in groups["explicit"]] == ["is_safe#ex1", "is_safe#ex2", "f#ex1"]
    assert [g["test"]["id"] for g in groups["derived"]] == ["is_safe#derived1"]
    assert groups["heuristic"] == []
    assert [g["test"]["id"] for g in groups["scripts"]] == ["hello#session1"]


def test_reparse(harness_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    parser = ParseRecorder()
    h = harness_factory(make_services(parse_subject=parser))
    view = upload(h).json()

    r = h.client.post(f"/api/subjects/{view['id']}/reparse", json={})
    assert r.status_code == 200
    assert len(parser.calls) == 2
    assert r.json()["created_at"] == view["created_at"]

    ai = h.client.post(f"/api/subjects/{view['id']}/reparse", json={"use_ai": True})
    assert ai.status_code == 400
    assert "disabled" in ai.json()["detail"]
    assert len(parser.calls) == 2   # the AI parser was never called

    h.client.put("/api/settings", json={"ai_enabled": True, "ai_consent_subject": True, "anthropic_api_key": "sk-x"})
    ok = h.client.post(f"/api/subjects/{view['id']}/reparse", json={"use_ai": True})
    assert ok.status_code == 200
    assert parser.calls[-1]["use_ai"] is True and parser.calls[-1]["api_key"] == "sk-x"


def test_reparse_without_raw_file(harness_factory) -> None:
    h = harness_factory()
    view = upload(h).json()
    Path(h.store.get_subject(view["id"]).raw_path).unlink()
    assert h.client.post(f"/api/subjects/{view['id']}/reparse").status_code == 409


def test_unknown_subject_is_404(harness_factory) -> None:
    h = harness_factory()
    assert h.client.get("/api/subjects/nope").status_code == 404
    assert h.client.get("/api/subjects/nope/tests").status_code == 404
    assert h.client.get("/api/subjects/nope/document").status_code == 404
    spec = PracticalSpec().model_dump(mode="json")
    assert h.client.put("/api/subjects/nope/spec", json=spec).status_code == 404


def test_spec_schema(harness_factory) -> None:
    h = harness_factory()
    schema = h.client.get("/api/spec/schema").json()
    assert "exercises" in schema["properties"]
