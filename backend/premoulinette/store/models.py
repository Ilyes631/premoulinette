"""Persisted records (ARCHITECTURE.md, ``store/``). Re-exported by :mod:`premoulinette.store.db`."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from premoulinette.spec.models import PracticalSpec


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Naive datetimes are taken as UTC; aware ones are converted to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SubjectRecord(BaseModel):
    id: str
    title: str
    source_name: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    spec: PracticalSpec
    document_text: str = ""
    document_html: str | None = None
    media_type: Literal["html", "markdown", "text", "pdf"]
    parse_warnings: list[str] = Field(default_factory=list)
    parser: str = "heuristic"
    raw_path: str | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return as_utc(v)


class ProjectRecord(BaseModel):
    id: str
    name: str
    source_kind: Literal["path", "zip", "upload", "demo"]
    source_path: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    snapshot_path: str
    file_count: int = 0
    python_files: int = 0

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return as_utc(v)


class Settings(BaseModel):
    sandbox_mode: Literal["auto", "docker", "local"] = "auto"
    local_mode_acknowledged: bool = False
    docker_image: str = "python:3.12-slim"
    ai_enabled: bool = False
    ai_model: str = "claude-sonnet-5-5"
    ai_consent_subject: bool = False
    ai_consent_code: bool = False
    # Stored locally only; the API must never return it (expose `has_api_key` instead).
    anthropic_api_key: str | None = None
    explanation_language: Literal["fr", "en"] = "fr"
    default_timeout_s: float = Field(default=5.0, gt=0, le=60)
