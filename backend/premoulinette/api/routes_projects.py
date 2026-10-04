"""Project endpoints: import (zip / folder upload / local path), view, read-only file viewer."""
from __future__ import annotations

import re
import uuid
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from premoulinette.api.context import AppContext, get_ctx
from premoulinette.api.uploads import check_content_length, read_limited, safe_filename, too_large
from premoulinette.api.views import ProjectListItem, ProjectView, project_list_item, project_view
from premoulinette.config import FILE_VIEW_MAX_BYTES, FOLDER_UPLOAD_MAX_BYTES, FOLDER_UPLOAD_MAX_FILES, ZIP_MAX_BYTES
from premoulinette.engine.snapshots import count_python_files, new_snapshot_dir, remove_tree
from premoulinette.store.db import ProjectRecord

router = APIRouter()

# Errors raised by project ingestion that describe a bad input (-> 400), not a server bug.
_INGEST_ERRORS = (ValueError, zipfile.BadZipFile, PermissionError, FileNotFoundError, NotADirectoryError)
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_LANGUAGES = {
    ".py": "python", ".md": "markdown", ".markdown": "markdown", ".txt": "text", ".json": "json",
    ".html": "html", ".htm": "html", ".toml": "toml", ".yml": "yaml", ".yaml": "yaml", ".cfg": "ini",
    ".ini": "ini", ".sh": "shell", ".csv": "csv",
}
_MODES_HINT = "Send exactly one of: a zip archive ('file'), a folder upload ('files' + 'paths') or a local folder ('path')."


@router.post("/projects", response_model=ProjectView)
async def create_project(request: Request, ctx: AppContext = Depends(get_ctx)) -> ProjectView:
    check_content_length(request, max(ZIP_MAX_BYTES, FOLDER_UPLOAD_MAX_BYTES), "Project upload")
    async with request.form(max_files=FOLDER_UPLOAD_MAX_FILES + 1, max_fields=FOLDER_UPLOAD_MAX_FILES + 16) as form:
        archive = form.get("file")
        files = [f for f in form.getlist("files") if isinstance(f, UploadFile)]
        paths = [p for p in form.getlist("paths") if isinstance(p, str)]
        local = form.get("path")
        local = local.strip() if isinstance(local, str) else ""
        name_field = form.get("name")
        name = name_field.strip()[:120] if isinstance(name_field, str) and name_field.strip() else None

        if sum((isinstance(archive, UploadFile), bool(files), bool(local))) != 1:
            raise HTTPException(status_code=400, detail=_MODES_HINT)
        if isinstance(archive, UploadFile):
            data = await read_limited(archive, ZIP_MAX_BYTES, "Zip archive")
            zip_name = name or Path(safe_filename(archive.filename, default="project.zip")).stem
            return await run_in_threadpool(
                _create, ctx, "zip", None, zip_name,
                lambda dest: ctx.services.snapshot_from_zip(data, dest, zip_name),
            )
        if files:
            entries = await _read_folder_upload(files, paths)
            upload_name = name or _upload_name(entries)
            return await run_in_threadpool(
                _create, ctx, "upload", None, upload_name,
                lambda dest: ctx.services.snapshot_from_upload(entries, dest, upload_name),
            )
    src = _validate_local_folder(ctx, local)
    return await run_in_threadpool(
        _create, ctx, "path", str(src), name or src.name,
        lambda dest: ctx.services.snapshot_from_path(src, dest, kind="path"),
    )


async def _read_folder_upload(files: list[UploadFile], paths: list[str]) -> list[tuple[str, bytes]]:
    if len(files) > FOLDER_UPLOAD_MAX_FILES:
        raise HTTPException(status_code=413, detail=f"Too many files (limit: {FOLDER_UPLOAD_MAX_FILES}).")
    if paths and len(paths) != len(files):
        raise HTTPException(status_code=400, detail="'paths' must contain exactly one entry per uploaded file.")
    entries: list[tuple[str, bytes]] = []
    total = 0
    for i, upload in enumerate(files):
        rel = paths[i] if paths else (upload.filename or "")
        data = await upload.read(FOLDER_UPLOAD_MAX_BYTES - total + 1)
        total += len(data)
        if total > FOLDER_UPLOAD_MAX_BYTES:
            raise too_large("Folder upload", FOLDER_UPLOAD_MAX_BYTES)
        entries.append((rel, data))
    return entries


def _upload_name(entries: list[tuple[str, bytes]]) -> str:
    for rel, _ in entries:
        parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
        if len(parts) > 1:
            return parts[0][:120]
    return "uploaded-project"


def _validate_local_folder(ctx: AppContext, raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise HTTPException(status_code=400, detail="Give the absolute path of the project folder.")
    try:
        src = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=400, detail=f"Folder not found: {raw}") from None
    if not src.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a folder: {raw}")
    data_root = ctx.paths.root.resolve()
    if src == data_root or src.is_relative_to(data_root) or data_root.is_relative_to(src):
        raise HTTPException(
            status_code=400,
            detail="This folder contains (or is inside) PréMoulinette's data directory: choose the project folder itself.",
        )
    return src


def _create(
    ctx: AppContext, kind: str, source_path: str | None, name: str, make_snapshot: Callable[[Path], Any]
) -> ProjectView:
    project_id = uuid.uuid4().hex
    dest = new_snapshot_dir(ctx.paths.snapshots, project_id)
    try:
        snap = make_snapshot(dest)
    except _INGEST_ERRORS as exc:
        remove_tree(dest.parent)
        raise HTTPException(status_code=400, detail=f"Could not import the project: {exc}") from exc
    root = Path(snap.root)
    tree = list(ctx.services.list_tree(root))
    rec = ProjectRecord(
        id=project_id, name=name or snap.name, source_kind=kind, source_path=source_path,
        created_at=datetime.now(timezone.utc), snapshot_path=str(root),
        file_count=snap.file_count, python_files=count_python_files(tree),
    )
    ctx.store.save_project(rec)
    warnings = list(snap.warnings)
    if snap.skipped:
        warnings.append(f"{len(snap.skipped)} item(s) were not copied: " + ", ".join(snap.skipped[:10]))
    return project_view(rec, ctx.services, warnings, tree=tree)


@router.get("/projects", response_model=list[ProjectListItem])
def list_projects(ctx: AppContext = Depends(get_ctx)) -> list[ProjectListItem]:
    return [project_list_item(r) for r in ctx.store.list_projects()]


@router.get("/projects/{project_id}", response_model=ProjectView)
def get_project(project_id: str, ctx: AppContext = Depends(get_ctx)) -> ProjectView:
    return project_view(ctx.project_or_404(project_id), ctx.services)


@router.get("/projects/{project_id}/file")
def project_file(
    project_id: str, path: str = Query(..., min_length=1, max_length=1024), ctx: AppContext = Depends(get_ctx)
) -> dict[str, Any]:
    """Read-only access to one text file of the latest snapshot (never outside it)."""
    rec = ctx.project_or_404(project_id)
    rel = clean_relative_path(path)
    root = Path(rec.snapshot_path).resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root) or target == root:
        raise HTTPException(status_code=400, detail="Invalid path: outside the project.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {rel}")
    size = target.stat().st_size
    if size > FILE_VIEW_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large to display (limit: {FILE_VIEW_MAX_BYTES // 1024} KB).")
    raw = target.read_bytes()
    if b"\x00" in raw:
        raise HTTPException(status_code=415, detail="Binary file: it cannot be displayed.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="This file is not valid UTF-8 text.") from None
    return {"path": rel, "content": content, "language": _LANGUAGES.get(PurePosixPath(rel).suffix.lower(), "text"), "size": size}


def clean_relative_path(raw: str) -> str:
    """Normalize a client-supplied relative POSIX path; reject traversal, absolute paths and .git."""
    value = raw.replace("\\", "/")
    if "\x00" in value or value.startswith("/") or _DRIVE_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid path: it must be relative to the project.")
    parts = [p for p in value.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise HTTPException(status_code=400, detail="Invalid path.")
    if ".git" in parts:
        raise HTTPException(status_code=403, detail="Git internals are not served.")
    return "/".join(parts)
