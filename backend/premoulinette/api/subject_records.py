"""Subject parsing -> :class:`SubjectRecord` (shared by the subject upload, reparse and demo routes)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from premoulinette.api.services import ApiServices
from premoulinette.spec.models import SpecMetadata
from premoulinette.store.db import SubjectRecord

log = logging.getLogger(__name__)

SUBJECT_EXTENSIONS = frozenset({".html", ".htm", ".md", ".markdown", ".txt", ".pdf"})
_DEFAULT_TITLE = SpecMetadata().title


def check_subject_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUBJECT_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported subject format {ext or '(no extension)'}: use HTML, Markdown, plain text or PDF.",
        )
    return ext


def parse_or_400(
    services: ApiServices, data: bytes, filename: str, *, use_ai: bool = False, api_key: str | None = None
) -> tuple[Any, Any]:
    """``parse_subject`` with unreadable documents reported as HTTP 400."""
    try:
        return services.parse_subject(data, filename, use_ai=use_ai, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Could not read the subject: {exc}") from exc


def record_from_parse(
    subject_id: str, filename: str, doc: Any, parsed: Any, raw_path: Path | None,
    *, created_at: datetime | None = None,
) -> SubjectRecord:
    spec = parsed.spec.model_copy(deep=True)
    meta = spec.metadata
    if meta.source_name is None:
        meta.source_name = filename
    if meta.source_sha256 is None:
        meta.source_sha256 = getattr(doc, "sha256", None)
    title = meta.title
    if (not title or title == _DEFAULT_TITLE) and getattr(doc, "title", None):
        title = doc.title
    warnings = list(dict.fromkeys([*getattr(doc, "warnings", []), *getattr(parsed, "warnings", [])]))
    now = datetime.now(timezone.utc)
    return SubjectRecord(
        id=subject_id,
        title=title or filename,
        source_name=filename,
        created_at=created_at or now,
        updated_at=now,
        spec=spec,
        document_text=doc.text,
        document_html=None,   # the UI renders the extracted text; raw HTML is never re-served
        media_type=doc.media_type,
        parse_warnings=warnings,
        parser=meta.parser,
        raw_path=str(raw_path) if raw_path is not None else None,
    )
