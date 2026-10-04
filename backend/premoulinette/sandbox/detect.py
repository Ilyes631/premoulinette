"""Docker availability detection (cached) and image download."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from premoulinette.sandbox.procutil import no_window_flags

DEFAULT_IMAGE = "python:3.12-slim"
CACHE_TTL_S = 30.0
PULL_TIMEOUT_S = 900.0

# Default Docker Desktop CLI locations: a server started BEFORE Docker was installed keeps its old PATH.
DOCKER_FALLBACK_PATHS: list[Path] = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
    Path("/usr/local/bin/docker"),
    Path("/opt/homebrew/bin/docker"),
]


def find_docker() -> str | None:
    """The docker CLI: on PATH, else a default Docker Desktop install location.

    When found outside PATH, its directory is appended to this process's PATH so that docker's
    helpers living next to it (e.g. ``docker-credential-desktop`` used by ``docker pull``) resolve too.
    """
    found = shutil.which("docker")
    if found:
        return found
    for candidate in DOCKER_FALLBACK_PATHS:
        if candidate.is_file():
            bin_dir = str(candidate.parent)
            if bin_dir not in os.environ.get("PATH", "").split(os.pathsep):
                os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + bin_dir
            return str(candidate)
    return None


class DockerStatus(BaseModel):
    available: bool
    version: str | None = None
    image: str
    image_ready: bool = False
    error: str | None = None


Runner = Callable[[list[str], float], subprocess.CompletedProcess]

_cache: dict[str, tuple[float, DockerStatus]] = {}
_cache_lock = threading.Lock()


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, creationflags=no_window_flags(),
    )


def _first_line(data: bytes | str | None) -> str:
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else (data or "")
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[0][:300] if lines else ""


def _probe(image: str, timeout: float, docker: str, run: Runner) -> DockerStatus:
    try:
        proc = run([docker, "version", "--format", "{{.Server.Version}}"], timeout)
    except subprocess.TimeoutExpired:
        return DockerStatus(available=False, image=image, error="the Docker daemon did not answer in time")
    except OSError as exc:
        return DockerStatus(available=False, image=image, error=f"cannot run docker: {exc}")
    version = _first_line(proc.stdout)
    if proc.returncode != 0 or not version:
        reason = _first_line(proc.stderr) or f"docker version exited with code {proc.returncode}"
        return DockerStatus(available=False, image=image, error=f"the Docker daemon is not reachable: {reason}")
    try:
        inspect = run([docker, "image", "inspect", "--format", "{{.Id}}", image], timeout)
        image_ready = inspect.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        image_ready = False
    return DockerStatus(available=True, version=version, image=image, image_ready=image_ready)


def detect_docker(image: str = DEFAULT_IMAGE, timeout: float = 4.0, *, use_cache: bool = True,
                  run: Runner | None = None) -> DockerStatus:
    """Is Docker usable, and is ``image`` present locally? Results are cached for 30 s per image."""
    now = time.monotonic()
    if use_cache:
        with _cache_lock:
            hit = _cache.get(image)
            if hit is not None and now - hit[0] < CACHE_TTL_S:
                return hit[1].model_copy()
    docker = find_docker()
    if docker is None:
        status = DockerStatus(available=False, image=image, error="Docker is not installed (docker command not found)")
    else:
        status = _probe(image, timeout, docker, run or _run)
    with _cache_lock:
        _cache[image] = (time.monotonic(), status)
    return status.model_copy()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def pull_image(image: str, *, timeout: float = PULL_TIMEOUT_S, run: Runner | None = None) -> tuple[bool, str]:
    """``docker pull <image>``. Returns (ok, human-readable message)."""
    docker = find_docker()
    if docker is None:
        return False, "Docker is not installed (docker command not found)"
    try:
        proc = (run or _run)([docker, "pull", image], timeout)
    except subprocess.TimeoutExpired:
        return False, f"docker pull {image} did not finish within {timeout:g} s"
    except OSError as exc:
        return False, f"cannot run docker: {exc}"
    finally:
        with _cache_lock:
            _cache.pop(image, None)
    if proc.returncode != 0:
        return False, _first_line(proc.stderr) or f"docker pull exited with code {proc.returncode}"
    return True, f"Image {image} is ready."
