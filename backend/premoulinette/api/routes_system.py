"""Health, settings and sandbox preparation endpoints."""
from __future__ import annotations

import logging
import platform
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from premoulinette import __version__
from premoulinette.api.context import AppContext, api_key_of, get_ctx
from premoulinette.api.views import settings_view
from premoulinette.engine.jobs import JobError, ProgressFn
from premoulinette.engine.sandbox_select import decide_sandbox
from premoulinette.store.db import Settings

log = logging.getLogger(__name__)
router = APIRouter()

_READ_ONLY_FIELDS = frozenset({"has_api_key", "api_key_source"})
# The image name is passed to the docker CLI: forbid anything that could be read as an option.
_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,199}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")


@router.get("/health")
def health(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    settings = ctx.store.get_settings()
    docker: Any = None
    error: str | None = None
    try:
        docker = ctx.services.detect_docker(settings.docker_image)
    except Exception as exc:  # noqa: BLE001 - health must always answer
        log.warning("Docker detection failed: %s", exc)
        error = f"Docker detection failed: {exc}"
    decision = decide_sandbox(settings, docker)
    docker_view = (
        docker.model_dump(mode="json") if docker is not None
        else {"available": False, "version": None, "image": settings.docker_image, "image_ready": False, "error": error}
    )
    return {
        "ok": True,
        "version": __version__,
        "python": platform.python_version(),
        "docker": docker_view,
        "sandbox_mode": settings.sandbox_mode,
        "sandbox_mode_effective": decision.mode or "none",
        "sandbox_note": decision.reason,
        "ai": {"configured": api_key_of(settings) is not None, "enabled": settings.ai_enabled},
    }


@router.get("/settings")
def get_settings(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return settings_view(ctx.store.get_settings())


@router.put("/settings")
def put_settings(body: dict[str, Any] = Body(...), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """Partial update. ``anthropic_api_key``: absent = keep, ``null``/``""`` = remove, string = set."""
    updates = {k: v for k, v in body.items() if k not in _READ_ONLY_FIELDS}
    unknown = sorted(set(updates) - set(Settings.model_fields))
    if unknown:
        raise HTTPException(status_code=422, detail=[
            {"loc": ["body", k], "msg": "Unknown setting", "type": "extra_forbidden"} for k in unknown
        ])
    merged = ctx.store.get_settings().model_dump()
    if "anthropic_api_key" in updates:
        key = updates.pop("anthropic_api_key")
        merged["anthropic_api_key"] = (key.strip() or None) if isinstance(key, str) else key
    merged.update(updates)
    try:
        settings = Settings.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=[
            {"loc": ["body", *e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]) from exc
    problems = _semantic_problems(settings)
    if problems:
        raise HTTPException(status_code=422, detail=problems)
    ctx.store.save_settings(settings)
    return settings_view(settings)


def _semantic_problems(s: Settings) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []

    def add(field: str, msg: str) -> None:
        problems.append({"loc": ["body", field], "msg": msg, "type": "value_error"})

    if not _IMAGE_RE.match(s.docker_image):
        add("docker_image", "Invalid Docker image name.")
    if not _MODEL_RE.match(s.ai_model):
        add("ai_model", "Invalid model name.")
    if s.sandbox_mode == "local" and not s.local_mode_acknowledged:
        add("local_mode_acknowledged", "Developer mode must be acknowledged to use the local sandbox.")
    return problems


@router.post("/sandbox/prepare")
def prepare_sandbox(ctx: AppContext = Depends(get_ctx)) -> dict[str, str]:
    image = ctx.store.get_settings().docker_image
    pull_image = ctx.services.pull_image

    def job(progress: ProgressFn) -> None:
        progress("pull", 0.05)
        ok, message = pull_image(image)
        if not ok:
            raise JobError(message or f"Could not download the Docker image {image}.")
        return None

    state = ctx.jobs.submit("sandbox_prepare", [("pull", f"Downloading {image}…")], job)
    return {"job_id": state.id}
