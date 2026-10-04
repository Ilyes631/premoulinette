"""Upload helpers: size limits and safe file names."""
from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile

from premoulinette.config import MB

_MULTIPART_OVERHEAD = 1 * MB
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def too_large(what: str, limit: int) -> HTTPException:
    return HTTPException(status_code=413, detail=f"{what} is too large (limit: {limit // MB} MB).")


def check_content_length(request: Request, limit: int, what: str) -> None:
    """Reject early when the declared body size is clearly above ``limit``."""
    raw = request.headers.get("content-length", "")
    if raw.isdigit() and int(raw) > limit + _MULTIPART_OVERHEAD:
        raise too_large(what, limit)


async def read_limited(upload: UploadFile, limit: int, what: str) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise too_large(what, limit)
    return data


def safe_filename(name: str | None, default: str = "file") -> str:
    """Base name only, restricted charset, bounded length (keeps the extension)."""
    base = PureWindowsPath(PurePosixPath(name or "").name).name
    cleaned = _UNSAFE_CHARS.sub("_", base).strip("._")
    if not cleaned:
        return default
    if len(cleaned) > 120:
        stem, dot, ext = cleaned.rpartition(".")
        cleaned = (stem[: 110] + dot + ext[:9]) if dot else cleaned[:120]
    return cleaned
