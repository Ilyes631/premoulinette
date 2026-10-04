from __future__ import annotations

import pytest

from premoulinette.engine.sandbox_select import NO_DOCKER_MESSAGE, decide_sandbox
from premoulinette.store.db import Settings
from test_api_fakes import FakeDockerStatus

READY = FakeDockerStatus(available=True, image_ready=True, error=None, version="27.0")
NO_IMAGE = FakeDockerStatus(available=True, image_ready=False, error=None, version="27.0")
NO_DOCKER = FakeDockerStatus(available=False, error="docker: command not found")


@pytest.mark.parametrize(
    ("mode", "ack", "docker", "expected"),
    [
        ("auto", False, READY, "docker"),
        ("auto", True, READY, "docker"),
        ("auto", True, NO_DOCKER, "local"),
        ("auto", True, NO_IMAGE, "local"),
        ("auto", True, None, "local"),
        ("auto", False, NO_DOCKER, None),
        ("auto", False, NO_IMAGE, None),
        ("docker", True, READY, "docker"),
        ("docker", True, NO_DOCKER, None),
        ("docker", True, NO_IMAGE, None),
        ("local", True, None, "local"),
        ("local", True, READY, "local"),
        ("local", False, READY, None),
    ],
)
def test_decision_table(mode: str, ack: bool, docker: FakeDockerStatus | None, expected: str | None) -> None:
    decision = decide_sandbox(Settings(sandbox_mode=mode, local_mode_acknowledged=ack), docker)
    assert decision.mode == expected
    assert decision.reason


def test_messages() -> None:
    assert decide_sandbox(Settings(), NO_DOCKER).reason == NO_DOCKER_MESSAGE
    assert decide_sandbox(Settings(), None).reason == NO_DOCKER_MESSAGE
    assert "Prepare sandbox" in decide_sandbox(Settings(), NO_IMAGE).reason
    docker_only = decide_sandbox(Settings(sandbox_mode="docker"), NO_DOCKER).reason
    assert "command not found" in docker_only
    fallback = decide_sandbox(Settings(local_mode_acknowledged=True), NO_DOCKER)
    assert fallback.fallback is True
    assert decide_sandbox(Settings(local_mode_acknowledged=True), READY).fallback is False
