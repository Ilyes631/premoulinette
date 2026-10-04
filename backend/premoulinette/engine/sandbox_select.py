"""Choice of the execution sandbox from the user settings and the Docker status.

Shared by the pipeline (which fails the analysis when no sandbox may be used) and by
``GET /api/health`` (``sandbox_mode_effective``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

NO_DOCKER_MESSAGE = "Docker is not available. Enable Developer mode in Settings to run locally."


@dataclass(frozen=True)
class SandboxDecision:
    mode: Literal["docker", "local"] | None   # None = analysis cannot run student code
    reason: str                                 # error message when mode is None, else a short note
    fallback: bool = False                      # True when "auto" fell back to the local sandbox


def _docker_ready(status: Any) -> tuple[bool, bool, str | None]:
    """(available, image_ready, error) from a DockerStatus-like object (None = unknown)."""
    if status is None:
        return False, False, None
    return bool(getattr(status, "available", False)), bool(getattr(status, "image_ready", False)), getattr(
        status, "error", None
    )


def decide_sandbox(settings: Any, docker_status: Any | None) -> SandboxDecision:
    mode = settings.sandbox_mode
    acknowledged = bool(settings.local_mode_acknowledged)
    image = settings.docker_image
    available, image_ready, error = _docker_ready(docker_status)

    if mode == "local":
        if acknowledged:
            return SandboxDecision("local", "Developer mode (local sandbox) selected in Settings.")
        return SandboxDecision(
            None, "Local mode is selected but Developer mode has not been acknowledged in Settings."
        )

    if available and image_ready:
        return SandboxDecision("docker", f"Docker sandbox ({image}).")

    image_missing = (
        f"The Docker image {image} is not downloaded yet. Use 'Prepare sandbox' in Settings to download it."
    )
    if mode == "docker":
        if available:
            return SandboxDecision(None, image_missing)
        detail = f" ({error})" if error else ""
        return SandboxDecision(None, f"Docker is not available{detail}. Start Docker or switch the sandbox mode in Settings.")

    # auto
    if acknowledged:
        why = "the Docker image is not downloaded" if available else "Docker is not available"
        return SandboxDecision("local", f"Developer mode (local sandbox) used because {why}.", fallback=True)
    if available:
        return SandboxDecision(None, f"{image_missing} Or enable Developer mode in Settings to run locally.")
    return SandboxDecision(None, NO_DOCKER_MESSAGE)
