from __future__ import annotations

import pytest

from premoulinette.api.security import host_allowed, host_name, origin_allowed
from test_api_fakes import harness_factory  # noqa: F401  (fixture)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("localhost", "localhost"), ("localhost:8765", "localhost"), ("127.0.0.1:5173", "127.0.0.1"),
        ("[::1]:8765", "[::1]"), ("[::1]", "[::1]"), ("LOCALHOST:1", "localhost"),
        ("localhost:abc", None), ("[::1", None), ("localhost:", None), ("", None),
    ],
)
def test_host_name_parsing(header: str, expected: str | None) -> None:
    assert host_name(header) == expected


@pytest.mark.parametrize(
    "header", ["evil.example", "evil.example:8765", "localhost.evil.example", "127.0.0.1.nip.io", "0.0.0.0:8765", "[::2]:8765"]
)
def test_foreign_hosts_are_not_allowed(header: str) -> None:
    assert not host_allowed(header)


def test_origin_rules() -> None:
    assert origin_allowed("http://localhost:5173", "127.0.0.1:8765")
    assert origin_allowed("http://127.0.0.1:8765", "127.0.0.1:8765")   # same origin (built SPA)
    assert not origin_allowed("http://evil.example", "127.0.0.1:8765")
    assert not origin_allowed("null", "127.0.0.1:8765")


def test_bad_host_is_rejected(harness_factory) -> None:
    h = harness_factory()
    r = h.client.get("/api/health", headers={"Host": "evil.example:8765"})
    assert r.status_code == 403
    assert "host" in r.json()["detail"].lower()


@pytest.mark.parametrize("host", ["localhost:8765", "127.0.0.1:8765", "[::1]:8765", "localhost"])
def test_local_hosts_are_accepted(harness_factory, host: str) -> None:
    h = harness_factory()
    assert h.client.get("/api/health", headers={"Host": host}).status_code == 200


def test_dns_rebinding_post_is_rejected_even_with_header(harness_factory) -> None:
    h = harness_factory()
    r = h.client.post("/api/demo/load", json={"variant": "buggy"}, headers={"Host": "attacker.example"})
    assert r.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/api/analyses", {"subject_id": "x", "project_id": "y"}),
        ("PUT", "/api/settings", {"ai_enabled": True}),
        ("POST", "/api/demo/load", {"variant": "buggy"}),
        ("POST", "/api/sandbox/prepare", None),
    ],
)
def test_mutations_require_custom_header(harness_factory, method: str, path: str, payload: object) -> None:
    h = harness_factory()
    r = h.bare.request(method, path, json=payload)
    assert r.status_code == 403
    assert "X-PreMoulinette" in r.json()["detail"]
    # nothing was changed
    assert h.store.get_settings().ai_enabled is False


def test_wrong_header_value_is_rejected(harness_factory) -> None:
    h = harness_factory()
    r = h.bare.put("/api/settings", json={"ai_enabled": True}, headers={"X-PreMoulinette": "yes"})
    assert r.status_code == 403


def test_get_does_not_require_header(harness_factory) -> None:
    h = harness_factory()
    assert h.bare.get("/api/settings").status_code == 200


def test_foreign_origin_mutation_is_rejected(harness_factory) -> None:
    h = harness_factory()
    r = h.client.put("/api/settings", json={"ai_enabled": True}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    ok = h.client.put("/api/settings", json={"explanation_language": "en"}, headers={"Origin": "http://localhost:5173"})
    assert ok.status_code == 200


def test_cors_preflight_for_vite_origin(harness_factory) -> None:
    h = harness_factory()
    r = h.bare.options(
        "/api/settings",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,x-premoulinette",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-premoulinette" in r.headers["access-control-allow-headers"].lower()
    assert "PUT" in r.headers["access-control-allow-methods"]


def test_cors_preflight_rejects_other_origins(harness_factory) -> None:
    h = harness_factory()
    r = h.bare.options(
        "/api/settings",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_simple_cors_request_headers(harness_factory) -> None:
    h = harness_factory()
    allowed = h.bare.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    denied = h.bare.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in denied.headers


def test_unknown_api_path_is_json_404(harness_factory) -> None:
    h = harness_factory()
    r = h.client.get("/api/does-not-exist")
    assert r.status_code == 404
