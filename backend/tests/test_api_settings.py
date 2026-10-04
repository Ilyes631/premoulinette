from __future__ import annotations

import pytest

from test_api_fakes import harness_factory  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_defaults_are_redacted(harness_factory) -> None:
    h = harness_factory()
    data = h.client.get("/api/settings").json()
    assert data["sandbox_mode"] == "auto"
    assert data["local_mode_acknowledged"] is False
    assert data["has_api_key"] is False
    assert data["api_key_source"] is None
    assert "anthropic_api_key" not in data


def test_partial_update_roundtrip(harness_factory) -> None:
    h = harness_factory()
    r = h.client.put("/api/settings", json={"sandbox_mode": "docker", "explanation_language": "en", "default_timeout_s": 8})
    assert r.status_code == 200, r.text
    again = h.client.get("/api/settings").json()
    assert again["sandbox_mode"] == "docker"
    assert again["explanation_language"] == "en"
    assert again["default_timeout_s"] == 8
    assert again["ai_enabled"] is False   # untouched fields keep their value
    assert h.store.get_settings().sandbox_mode == "docker"


def test_api_key_is_stored_but_never_returned(harness_factory) -> None:
    h = harness_factory()
    secret = "sk-ant-test-0123456789"
    r = h.client.put("/api/settings", json={"anthropic_api_key": f"  {secret} ", "ai_enabled": True})
    assert r.status_code == 200
    assert secret not in r.text
    assert r.json()["has_api_key"] is True
    assert r.json()["api_key_source"] == "settings"
    assert h.store.get_settings().anthropic_api_key == secret
    got = h.client.get("/api/settings")
    assert secret not in got.text
    assert secret not in h.client.get("/api/health").text

    # GET -> modify -> PUT round trip (no key field) keeps the key
    body = got.json()
    body["explanation_language"] = "en"
    assert h.client.put("/api/settings", json=body).status_code == 200
    assert h.store.get_settings().anthropic_api_key == secret

    # explicit null removes it
    r = h.client.put("/api/settings", json={"anthropic_api_key": None})
    assert r.json()["has_api_key"] is False
    assert h.store.get_settings().anthropic_api_key is None


def test_env_key_is_reported(harness_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    h = harness_factory()
    data = h.client.get("/api/settings").json()
    assert data["has_api_key"] is True
    assert data["api_key_source"] == "env"
    assert "sk-env" not in h.client.get("/api/settings").text


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"sandbox_mode": "weird"}, "sandbox_mode"),
        ({"default_timeout_s": 0}, "default_timeout_s"),
        ({"default_timeout_s": 600}, "default_timeout_s"),
        ({"explanation_language": "de"}, "explanation_language"),
        ({"docker_image": "--privileged"}, "docker_image"),
        ({"docker_image": "python:3.12 ; rm -rf /"}, "docker_image"),
        ({"ai_model": "x y"}, "ai_model"),
        ({"sandbox_mode": "local"}, "local_mode_acknowledged"),
        ({"not_a_setting": 1}, "not_a_setting"),
        ({"ai_enabled": "maybe"}, "ai_enabled"),
    ],
)
def test_invalid_settings_are_rejected(harness_factory, payload: dict, field: str) -> None:
    h = harness_factory()
    before = h.store.get_settings()
    r = h.client.put("/api/settings", json=payload)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert any(field in [str(x) for x in d["loc"]] for d in detail), detail
    assert all({"loc", "msg"} <= set(d) for d in detail)
    assert h.store.get_settings() == before


def test_local_mode_with_acknowledgement(harness_factory) -> None:
    h = harness_factory()
    r = h.client.put("/api/settings", json={"sandbox_mode": "local", "local_mode_acknowledged": True})
    assert r.status_code == 200
    health = h.client.get("/api/health").json()
    assert health["sandbox_mode_effective"] == "local"


def test_read_only_fields_are_ignored(harness_factory) -> None:
    h = harness_factory()
    r = h.client.put("/api/settings", json={"has_api_key": True, "api_key_source": "settings"})
    assert r.status_code == 200
    assert r.json()["has_api_key"] is False


def test_health_reports_docker_and_effective_mode(harness_factory) -> None:
    h = harness_factory()
    data = h.client.get("/api/health").json()
    assert data["ok"] is True
    assert data["version"]
    assert data["python"]
    assert data["docker"]["available"] is False
    assert data["sandbox_mode_effective"] == "none"
    assert "Developer mode" in data["sandbox_note"]
    assert data["ai"] == {"configured": False, "enabled": False}


def test_health_survives_docker_detection_crash(harness_factory) -> None:
    from test_api_fakes import make_services

    def boom(*_a, **_k):
        raise RuntimeError("daemon exploded")

    h = harness_factory(make_services(detect_docker=boom))
    data = h.client.get("/api/health").json()
    assert data["docker"]["available"] is False
    assert "daemon exploded" in data["docker"]["error"]


def test_sandbox_prepare_job(harness_factory) -> None:
    import time

    from test_api_fakes import make_services

    pulled: list[str] = []
    h = harness_factory(make_services(pull_image=lambda image: (pulled.append(image) or True, "ok")))
    job_id = h.client.post("/api/sandbox/prepare").json()["job_id"]
    deadline = time.monotonic() + 10
    while (state := h.client.get(f"/api/jobs/{job_id}").json())["status"] not in ("done", "error"):
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert state["status"] == "done"
    assert pulled == ["python:3.12-slim"]

    h2 = harness_factory(make_services(pull_image=lambda image: (False, "pull access denied")))
    job_id = h2.client.post("/api/sandbox/prepare").json()["job_id"]
    deadline = time.monotonic() + 10
    while (state := h2.client.get(f"/api/jobs/{job_id}").json())["status"] not in ("done", "error"):
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert state["status"] == "error"
    assert state["error"] == "pull access denied"
