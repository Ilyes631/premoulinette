"""Docker sandbox: command hardening, factory, failure paths, detection (no Docker needed)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from premoulinette.runner.models import FunctionJob, RunPlan
from premoulinette.sandbox import detect
from premoulinette.sandbox.base import Sandbox, get_sandbox
from premoulinette.sandbox.docker import DockerSandbox, build_docker_command, validate_image
from premoulinette.sandbox.local import LocalSandbox


def _pairs(cmd: list[str]) -> list[tuple[str, str]]:
    return list(zip(cmd, cmd[1:]))


def test_build_docker_command_has_every_hardening_flag(tmp_path: Path):
    snap, harness, plan_dir = tmp_path / "work", tmp_path / "harness", tmp_path / "plan"
    cmd = build_docker_command(snap, harness, plan_dir, "python:3.12-slim", "premoulinette-abc")
    assert cmd[:2] == ["docker", "run"]
    for flag in ("--rm", "--read-only"):
        assert flag in cmd
    pairs = _pairs(cmd)
    for pair in [
        ("--network", "none"),
        ("--tmpfs", "/tmp:rw,size=64m,exec"),
        ("--memory", "256m"),
        ("--memory-swap", "256m"),
        ("--cpus", "1"),
        ("--pids-limit", "128"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges"),
        ("--user", "65534:65534"),
        ("--name", "premoulinette-abc"),
        ("-v", f"{snap}:/work:ro"),
        ("-v", f"{harness}:/harness:ro"),
        ("-v", f"{plan_dir}:/plan:ro"),
        ("-w", "/work"),
    ]:
        assert pair in pairs, pair
    image_at = cmd.index("python:3.12-slim")
    assert cmd[image_at + 1:] == ["python", "/harness/run_plan.py", "/plan/plan.json"]
    # every option comes before the image (after it, words are the container's command)
    assert all(not arg.startswith("-") for arg in cmd[image_at:])
    assert "--privileged" not in cmd and "host" not in cmd


@pytest.mark.parametrize("image", ["--privileged", "-v", "", "a b", "img;rm -rf /", "x/../y", "$(id)"])
def test_invalid_images_are_rejected(image: str, tmp_path: Path):
    with pytest.raises(ValueError):
        validate_image(image)
    with pytest.raises(ValueError):
        build_docker_command(tmp_path, tmp_path, tmp_path, image, "premoulinette-x")


def test_valid_image_references():
    for image in ("python:3.12-slim", "ghcr.io/org/py@sha256:abc123", "localhost:5000/py:3.13"):
        assert validate_image(image) == image


def test_invalid_container_name(tmp_path: Path):
    with pytest.raises(ValueError):
        build_docker_command(tmp_path, tmp_path, tmp_path, "python:3.12-slim", "--rm")


def test_factory():
    docker = get_sandbox("docker", image="python:3.13-slim")
    local = get_sandbox("local")
    assert isinstance(docker, DockerSandbox) and docker.mode == "docker" and docker.image == "python:3.13-slim"
    assert isinstance(local, LocalSandbox) and local.mode == "local"
    assert isinstance(docker, Sandbox) and isinstance(local, Sandbox)
    with pytest.raises(ValueError):
        get_sandbox("vm")  # type: ignore[arg-type]


def test_docker_info():
    info = DockerSandbox("python:3.12-slim").info()
    assert info.mode == "docker" and info.image == "python:3.12-slim" and info.network is False
    assert info.limits["memory"] == "256m" and info.limits["pids"] == 128


PLAN = RunPlan(jobs=[FunctionJob(id="a", module_path="m.py", function="f"),
                     FunctionJob(id="b", module_path="m.py", function="g")])


def test_missing_docker_cli_gives_harness_errors(tmp_path: Path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    results = DockerSandbox(docker=str(tmp_path / "no-such-docker.exe")).run(PLAN, tmp_path)
    assert [r.id for r in results.results] == ["a", "b"]
    assert all(r.status == "harness_error" and r.harness_error for r in results.results)
    assert results.errors and results.sandbox_mode == "docker"


def test_invalid_image_gives_harness_errors(tmp_path: Path):
    results = DockerSandbox(image="--privileged").run(PLAN, tmp_path)
    assert all(r.status == "harness_error" for r in results.results)
    assert "invalid Docker image" in results.errors[0]


# ---------------------------------------------------------------------------------------------
# detect.py
# ---------------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_cache():
    detect.clear_cache()
    yield
    detect.clear_cache()


def test_detect_without_docker_is_fast(monkeypatch):
    monkeypatch.setattr(detect.shutil, "which", lambda name: None)
    monkeypatch.setattr(detect, "DOCKER_FALLBACK_PATHS", [])
    status = detect.detect_docker("python:3.12-slim")
    assert status.available is False and status.image_ready is False
    assert status.error and "not installed" in status.error
    assert detect.pull_image("python:3.12-slim")[0] is False


def test_find_docker_falls_back_to_default_install_location(monkeypatch, tmp_path):
    fake = tmp_path / "Docker" / "resources" / "bin" / "docker.exe"
    fake.parent.mkdir(parents=True)
    fake.write_bytes(b"")
    monkeypatch.setattr(detect.shutil, "which", lambda name: None)
    monkeypatch.setattr(detect, "DOCKER_FALLBACK_PATHS", [tmp_path / "missing.exe", fake])
    monkeypatch.setenv("PATH", "C:\\nothing")
    assert detect.find_docker() == str(fake)
    assert str(fake.parent) in detect.os.environ["PATH"].split(detect.os.pathsep)   # helpers next to it resolve


def test_detect_with_fake_docker_and_cache(monkeypatch):
    monkeypatch.setattr(detect.shutil, "which", lambda name: "/usr/bin/docker")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
        calls.append(cmd)
        if cmd[1] == "version":
            return subprocess.CompletedProcess(cmd, 0, b"27.1.1\n", b"")
        return subprocess.CompletedProcess(cmd, 1, b"", b"No such image")

    status = detect.detect_docker("python:3.12-slim", run=fake_run)
    assert (status.available, status.version, status.image_ready) == (True, "27.1.1", False)
    again = detect.detect_docker("python:3.12-slim", run=fake_run)
    assert again == status and len(calls) == 2  # cached: no new docker call


def test_detect_daemon_down(monkeypatch):
    monkeypatch.setattr(detect.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 1, b"", b"Cannot connect to the Docker daemon\n")

    status = detect.detect_docker("python:3.12-slim", run=fake_run)
    assert status.available is False and "daemon" in (status.error or "")


def test_detect_timeout(monkeypatch):
    monkeypatch.setattr(detect.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd, timeout)

    status = detect.detect_docker("python:3.12-slim", timeout=0.1, run=fake_run)
    assert status.available is False and status.error


def test_pull_image_result(monkeypatch):
    monkeypatch.setattr(detect.shutil, "which", lambda name: "/usr/bin/docker")
    ok = detect.pull_image("python:3.12-slim", run=lambda cmd, t: subprocess.CompletedProcess(cmd, 0, b"", b""))
    bad = detect.pull_image("python:3.12-slim",
                            run=lambda cmd, t: subprocess.CompletedProcess(cmd, 1, b"", b"pull access denied\n"))
    assert ok[0] is True and bad == (False, "pull access denied")
