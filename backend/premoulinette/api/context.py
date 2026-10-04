"""Per-application state shared by the routes (``request.app.state.ctx``)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from premoulinette.api.services import ApiServices
from premoulinette.config import DataPaths
from premoulinette.engine.jobs import JobManager
from premoulinette.store.db import ProjectRecord, Settings, Store, SubjectRecord


@dataclass
class AppContext:
    paths: DataPaths
    store: Store
    jobs: JobManager
    services: ApiServices
    demo_dir: Path

    def subject_or_404(self, subject_id: str) -> SubjectRecord:
        rec = self.store.get_subject(subject_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Unknown subject {subject_id!r}")
        return rec

    def project_or_404(self, project_id: str) -> ProjectRecord:
        rec = self.store.get_project(project_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Unknown project {project_id!r}")
        return rec


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def api_key_of(settings: Settings) -> str | None:
    """API key from Settings, else the ``ANTHROPIC_API_KEY`` environment variable."""
    key = (settings.anthropic_api_key or "").strip() or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or None


def ai_blockers(settings: Settings, *, consent: str) -> list[str]:
    """Reasons why an AI call is not allowed (empty = allowed). ``consent``: "subject" or "code"."""
    problems: list[str] = []
    if not settings.ai_enabled:
        problems.append("AI features are disabled. Enable them in Settings.")
    if consent == "subject" and not settings.ai_consent_subject:
        problems.append("You have not consented to sending the subject to the AI provider (Settings).")
    if consent == "code" and not settings.ai_consent_code:
        problems.append("You have not consented to sending code excerpts to the AI provider (Settings).")
    if api_key_of(settings) is None:
        problems.append("No Anthropic API key is configured (Settings or ANTHROPIC_API_KEY).")
    return problems


def require_ai(settings: Settings, *, consent: str) -> str:
    problems = ai_blockers(settings, consent=consent)
    if problems:
        raise HTTPException(status_code=400, detail=" ".join(problems))
    key = api_key_of(settings)
    assert key is not None
    return key
