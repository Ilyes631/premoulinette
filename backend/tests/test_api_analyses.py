from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from premoulinette.engine.pipeline import STAGES, AnalysisError
from premoulinette.results.models import CheckResult
from test_api_fakes import harness_factory, make_project_dir, make_report, make_services  # noqa: F401

CHECK_ID = "structure:file:pkg/hello.py"
TEST_CHECK_ID = "test:is_safe#ex1"


def wait_job(h, job_id: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        state = h.client.get(f"/api/jobs/{job_id}").json()
        if state["status"] in ("done", "error"):
            return state
        assert time.monotonic() < deadline, state
        time.sleep(0.02)


class FakeRun:
    """Fake ``run_analysis``: reports every stage, saves a report, records its arguments."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    def __call__(self, subject, project, settings, store, progress, *, snapshots_dir: Path):
        self.calls.append({"subject": subject.id, "project": project.id, "settings": settings, "snapshots_dir": snapshots_dir})
        for key, _ in STAGES:
            progress(key, 0.5)
        if self.error is not None:
            raise self.error
        report = make_report(subject.id, project.id, number=store.next_number(subject.id, project.id),
                             report_id=f"rep{len(self.calls)}")
        store.save_analysis(report)
        return report


@pytest.fixture
def setup(harness_factory, tmp_path: Path):
    def make(run: FakeRun | None = None, **services: Any):
        run = run or FakeRun()
        h = harness_factory(make_services(run_analysis=run, **services))
        subject = h.client.post("/api/subjects", files={"file": ("s.html", b"<h1>x</h1>", "text/html")}).json()
        project = h.client.post("/api/projects", data={"path": str(make_project_dir(tmp_path / f"p{len(run.calls)}{id(h)}"))}).json()
        return h, run, subject["id"], project["id"]

    return make


def analyze(h, subject_id: str, project_id: str) -> dict[str, Any]:
    r = h.client.post("/api/analyses", json={"subject_id": subject_id, "project_id": project_id})
    assert r.status_code == 200, r.text
    return wait_job(h, r.json()["job_id"])


def test_analysis_job_lifecycle(setup) -> None:
    h, run, sid, pid = setup()
    state = analyze(h, sid, pid)
    assert state["status"] == "done", state
    assert state["kind"] == "analysis"
    assert state["progress"] == 1.0
    assert [s["key"] for s in state["stages"]] == [k for k, _ in STAGES]
    assert all(s["status"] == "done" for s in state["stages"])
    assert run.calls[0]["snapshots_dir"] == h.ctx.paths.snapshots

    report = h.client.get(f"/api/analyses/{state['result_id']}").json()
    assert report["id"] == state["result_id"]
    assert report["number"] == 1
    assert report["checks"][0]["id"] == TEST_CHECK_ID

    second = analyze(h, sid, pid)
    items = h.client.get("/api/analyses", params={"subject_id": sid, "project_id": pid}).json()
    assert [i["id"] for i in items] == [second["result_id"], state["result_id"]]
    assert [i["number"] for i in items] == [2, 1]
    assert h.client.get("/api/analyses", params={"subject_id": "other"}).json() == []
    assert len(h.client.get("/api/analyses", params={"limit": 1}).json()) == 1
    assert h.client.get("/api/analyses", params={"limit": 0}).status_code == 422

    cmp = h.client.get(f"/api/analyses/{second['result_id']}/compare/{state['result_id']}")
    assert cmp.status_code == 200
    assert cmp.json()["base_id"] == state["result_id"] and cmp.json()["head_id"] == second["result_id"]
    assert h.client.get(f"/api/analyses/{second['result_id']}/compare/nope").status_code == 404


def test_settings_are_passed_to_the_pipeline(setup) -> None:
    h, run, sid, pid = setup()
    h.client.put("/api/settings", json={"sandbox_mode": "local", "local_mode_acknowledged": True})
    analyze(h, sid, pid)
    assert run.calls[0]["settings"].sandbox_mode == "local"


def test_user_facing_pipeline_error(setup) -> None:
    message = "Docker is not available. Enable Developer mode in Settings to run locally."
    h, _, sid, pid = setup(FakeRun(error=AnalysisError(message)))
    state = analyze(h, sid, pid)
    assert state["status"] == "error"
    assert state["error"] == message
    assert state["result_id"] is None
    assert h.client.get("/api/analyses").json() == []


def test_unknown_subject_or_project(setup) -> None:
    h, _, sid, pid = setup()
    assert h.client.post("/api/analyses", json={"subject_id": "nope", "project_id": pid}).status_code == 404
    assert h.client.post("/api/analyses", json={"subject_id": sid, "project_id": "nope"}).status_code == 404
    assert h.client.post("/api/analyses", json={"subject_id": sid}).status_code == 422
    assert h.client.get("/api/jobs/nope").status_code == 404
    assert h.client.get("/api/analyses/nope").status_code == 404


@pytest.mark.parametrize(
    ("fmt", "media", "body"),
    [("json", "application/json", "JSON"), ("md", "text/markdown", "MD"), ("html", "text/html", "HTML")],
)
def test_export(setup, fmt: str, media: str, body: str) -> None:
    h, _, sid, pid = setup(
        to_json=lambda r: f"JSON {r.id}", to_markdown=lambda r: f"MD {r.id}", to_html=lambda r: f"HTML {r.id}"
    )
    state = analyze(h, sid, pid)
    r = h.client.get(f"/api/analyses/{state['result_id']}/export", params={"format": fmt})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(media)
    assert r.headers["content-disposition"] == f'attachment; filename="premoulinette-report-1.{fmt}"'
    assert r.text == f"{body} {state['result_id']}"


def test_export_rejects_unknown_format(setup) -> None:
    h, _, sid, pid = setup()
    state = analyze(h, sid, pid)
    assert h.client.get(f"/api/analyses/{state['result_id']}/export", params={"format": "exe"}).status_code == 422
    assert h.client.get("/api/analyses/nope/export").status_code == 404


class ExplainSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def make(self, name: str):
        def fn(*args: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls.append((name, args, kwargs))
            return {"title": name, "markdown": f"{name} text", "provider": "ai" if name == "ai" else "template",
                    "language": "fr", "sent_payload": None}
        return fn

    def services(self) -> dict[str, Any]:
        return {
            "explain": self.make("explain"), "how_to_fix": self.make("fix"),
            "expected_behavior": self.make("expected"), "explain_with_ai": self.make("ai"),
            "build_ai_payload": lambda check, mode, lang: {"rule": check.id, "mode": mode, "lang": lang},
        }


def explain_url(analysis_id: str, check_id: str, suffix: str = "explain") -> str:
    return f"/api/analyses/{analysis_id}/checks/{quote(check_id, safe='')}/{suffix}"


def test_explain_template_modes(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    spy = ExplainSpy()
    h, _, sid, pid = setup(**spy.services())
    aid = analyze(h, sid, pid)["result_id"]

    r = h.client.post(explain_url(aid, TEST_CHECK_ID), json={"mode": "explain"})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "explain"
    name, args, _ = spy.calls[-1]
    assert isinstance(args[0], CheckResult) and args[0].id == TEST_CHECK_ID
    assert args[1] == "fr"

    h.client.post(explain_url(aid, CHECK_ID), json={"mode": "fix", "lang": "en"})
    assert spy.calls[-1][0] == "fix" and spy.calls[-1][1][0].id == CHECK_ID and spy.calls[-1][1][1] == "en"

    h.client.post(explain_url(aid, CHECK_ID), json={"mode": "expected", "provider": "ai"})
    name, args, _ = spy.calls[-1]
    assert name == "expected"   # "expected" never calls the AI
    assert args[1].metadata.title == "Fake TP"

    assert h.client.post(explain_url(aid, "test:unknown"), json={}).status_code == 404
    assert h.client.post(explain_url("nope", CHECK_ID), json={}).status_code == 404


def test_explain_ai_requires_opt_in(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    spy = ExplainSpy()
    h, _, sid, pid = setup(**spy.services())
    aid = analyze(h, sid, pid)["result_id"]

    r = h.client.post(explain_url(aid, TEST_CHECK_ID), json={"mode": "explain", "provider": "ai"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "disabled" in detail and "consented" in detail and "API key" in detail
    assert not any(c[0] == "ai" for c in spy.calls)

    h.client.put("/api/settings", json={"ai_enabled": True, "ai_consent_code": True})
    assert h.client.post(explain_url(aid, TEST_CHECK_ID), json={"provider": "ai"}).status_code == 400

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-key")
    r = h.client.post(explain_url(aid, TEST_CHECK_ID), json={"mode": "fix", "provider": "ai", "lang": "en"})
    assert r.status_code == 200
    name, args, kwargs = spy.calls[-1]
    assert name == "ai"
    assert args[1:] == ("fix", "en", "sk-env-key")
    assert kwargs == {"model": "claude-sonnet-5-5"}


def test_ai_payload_preview(setup) -> None:
    spy = ExplainSpy()
    h, _, sid, pid = setup(**spy.services())
    aid = analyze(h, sid, pid)["result_id"]
    r = h.client.get(explain_url(aid, TEST_CHECK_ID, "ai-payload"), params={"mode": "fix"})
    assert r.status_code == 200
    assert r.json() == {"rule": TEST_CHECK_ID, "mode": "fix", "lang": "fr"}
    assert h.client.get(explain_url(aid, TEST_CHECK_ID, "ai-payload"), params={"mode": "nope"}).status_code == 422


def test_job_state_shape_while_running(setup) -> None:
    import threading

    gate = threading.Event()

    class SlowRun(FakeRun):
        def __call__(self, subject, project, settings, store, progress, *, snapshots_dir):
            progress("repository", 0.1)
            gate.wait(5)
            return super().__call__(subject, project, settings, store, progress, snapshots_dir=snapshots_dir)

    h, _, sid, pid = setup(SlowRun())
    job_id = h.client.post("/api/analyses", json={"subject_id": sid, "project_id": pid}).json()["job_id"]
    deadline = time.monotonic() + 5
    while (state := h.client.get(f"/api/jobs/{job_id}").json())["stage"] != "repository":
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert state["status"] == "running"
    assert [s["status"] for s in state["stages"][:3]] == ["done", "running", "pending"]
    assert state["progress"] == pytest.approx(0.1)
    gate.set()
    assert wait_job(h, job_id)["status"] == "done"


def test_check_ids_with_hash_need_encoding(setup) -> None:
    """Documented client contract: '#' must be percent-encoded, otherwise it is a URL fragment."""
    spy = ExplainSpy()
    h, _, sid, pid = setup(**spy.services())
    aid = analyze(h, sid, pid)["result_id"]
    raw = h.client.post(f"/api/analyses/{aid}/checks/{TEST_CHECK_ID}/explain", json={})
    assert raw.status_code in (404, 405)
    assert h.client.post(explain_url(aid, TEST_CHECK_ID), json={}).status_code == 200
