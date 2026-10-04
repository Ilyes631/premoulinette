"""Subject endpoints: upload, reparse, spec review/edit, generated tests, document text."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from premoulinette.api.context import AppContext, get_ctx, require_ai
from premoulinette.api.subject_records import check_subject_extension, parse_or_400, record_from_parse
from premoulinette.api.uploads import check_content_length, read_limited, safe_filename
from premoulinette.api.views import SubjectView, subject_view
from premoulinette.config import SUBJECT_MAX_BYTES
from premoulinette.spec.models import PracticalSpec

router = APIRouter()

_TEST_GROUPS = {"explicit_tests": "explicit", "derived_tests": "derived", "heuristic_tests": "heuristic"}


class ReparseRequest(BaseModel):
    use_ai: bool = False


@router.post("/subjects", response_model=SubjectView)
async def upload_subject(request: Request, ctx: AppContext = Depends(get_ctx)) -> SubjectView:
    check_content_length(request, SUBJECT_MAX_BYTES, "Subject file")
    async with request.form(max_files=1, max_fields=8) as form:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(status_code=400, detail="Send the subject as a multipart file field named 'file'.")
        filename = upload.filename or ""
        check_subject_extension(filename)
        data = await read_limited(upload, SUBJECT_MAX_BYTES, "Subject file")
    return await run_in_threadpool(_create_subject, ctx, data, filename)


def _create_subject(ctx: AppContext, data: bytes, filename: str) -> SubjectView:
    ext = check_subject_extension(filename)
    doc, parsed = parse_or_400(ctx.services, data, filename)
    subject_id = uuid.uuid4().hex
    raw_dir = ctx.paths.subjects / subject_id
    raw_dir.mkdir(parents=True, exist_ok=False)
    raw_path = raw_dir / safe_filename(filename, default=f"subject{ext}")
    raw_path.write_bytes(data)
    rec = record_from_parse(subject_id, Path(filename).name, doc, parsed, raw_path)
    ctx.store.save_subject(rec)
    return subject_view(rec, ctx.services)


@router.get("/subjects", response_model=list[SubjectView])
def list_subjects(ctx: AppContext = Depends(get_ctx)) -> list[SubjectView]:
    return [subject_view(r, ctx.services) for r in ctx.store.list_subjects()]


@router.get("/subjects/{subject_id}", response_model=SubjectView)
def get_subject(subject_id: str, ctx: AppContext = Depends(get_ctx)) -> SubjectView:
    return subject_view(ctx.subject_or_404(subject_id), ctx.services)


@router.post("/subjects/{subject_id}/reparse", response_model=SubjectView)
def reparse_subject(
    subject_id: str, body: ReparseRequest | None = None, ctx: AppContext = Depends(get_ctx)
) -> SubjectView:
    """Parse the original file again (discards manual spec edits)."""
    body = body or ReparseRequest()
    rec = ctx.subject_or_404(subject_id)
    raw = Path(rec.raw_path) if rec.raw_path else None
    if raw is None or not raw.is_file():
        raise HTTPException(status_code=409, detail="The original subject file is no longer available: upload it again.")
    api_key = require_ai(ctx.store.get_settings(), consent="subject") if body.use_ai else None
    doc, parsed = parse_or_400(ctx.services, raw.read_bytes(), rec.source_name, use_ai=body.use_ai, api_key=api_key)
    new = record_from_parse(rec.id, rec.source_name, doc, parsed, raw, created_at=rec.created_at)
    ctx.store.save_subject(new)
    return subject_view(new, ctx.services)


@router.put("/subjects/{subject_id}/spec", response_model=SubjectView)
def put_spec(subject_id: str, spec: PracticalSpec, ctx: AppContext = Depends(get_ctx)) -> SubjectView:
    """Save a spec edited in the UI; saving through the editor marks it as reviewed by the user."""
    ctx.subject_or_404(subject_id)
    spec = spec.model_copy(deep=True)
    spec.metadata.reviewed_by_user = True
    rec = ctx.store.update_spec(subject_id, spec)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Unknown subject {subject_id!r}")
    return subject_view(rec, ctx.services)


@router.get("/subjects/{subject_id}/tests")
def subject_tests(subject_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, list[Any]]:
    rec = ctx.subject_or_404(subject_id)
    fn_tests, script_tests = ctx.services.generate_tests(rec.spec)
    groups: dict[str, list[Any]] = {"explicit": [], "derived": [], "heuristic": [], "scripts": []}
    for gen in fn_tests:
        groups[_TEST_GROUPS.get(gen.category, "heuristic")].append(gen.model_dump(mode="json"))
    groups["scripts"] = [gen.model_dump(mode="json") for gen in script_tests]
    return groups


@router.get("/subjects/{subject_id}/document")
def subject_document(subject_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    rec = ctx.subject_or_404(subject_id)
    return {"text": rec.document_text, "html": rec.document_html, "media_type": rec.media_type}


@router.get("/spec/schema")
def spec_schema() -> dict[str, Any]:
    return PracticalSpec.model_json_schema()
