"""Subject file -> :class:`SubjectDocument` (HTML, Markdown, plain text, PDF)."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import PurePath

from premoulinette.subject.docbuilder import DocBuilder
from premoulinette.subject.document import MediaType, SubjectDocument
from premoulinette.subject.extract_html import extract_html
from premoulinette.subject.extract_markdown import extract_markdown
from premoulinette.subject.extract_text import extract_text
from premoulinette.subject.textutil import decode_bytes

MAX_SUBJECT_BYTES = 20 * 1024 * 1024

_EXTENSIONS: dict[str, MediaType] = {
    ".html": "html", ".htm": "html", ".xhtml": "html",
    ".md": "markdown", ".markdown": "markdown", ".mdown": "markdown",
    ".txt": "text", ".text": "text",
    ".pdf": "pdf",
}


class SubjectExtractionError(ValueError):
    pass


def detect_media_type(data: bytes, filename: str) -> MediaType:
    if data.lstrip()[:5] == b"%PDF-":
        return "pdf"
    ext = PurePath(filename).suffix.lower()
    if ext in _EXTENSIONS:
        return _EXTENSIONS[ext]
    head = data[:2048].lower()
    if b"<html" in head or b"<!doctype html" in head:
        return "html"
    return "text"


def _pdf_text(data: bytes) -> tuple[str, list[str]]:
    from pypdf import PdfReader  # lazy: only needed for PDFs
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise SubjectExtractionError(f"Could not read PDF: {exc}") from exc
    warnings: list[str] = []
    text = "\n\n".join(p.replace("\r\n", "\n").replace("\r", "\n") for p in pages)
    if not text.strip():
        warnings.append("No text could be extracted from the PDF (scanned document?).")
    else:
        warnings.append("PDF text extraction loses formatting (indentation, input markers): review the parsed spec.")
    return text, warnings


def extract_document(data: bytes, filename: str) -> SubjectDocument:
    """Extract a structured document from raw subject bytes (html/htm, md/markdown, txt, pdf)."""
    if len(data) > MAX_SUBJECT_BYTES:
        raise SubjectExtractionError(f"Subject file too large ({len(data)} bytes, max {MAX_SUBJECT_BYTES}).")
    media = detect_media_type(data, filename)
    builder = DocBuilder()
    warnings: list[str] = []
    if media == "pdf":
        text, warnings = _pdf_text(data)
        title = extract_text(text, builder)
    else:
        text, warnings = decode_bytes(data)
        if media == "html":
            title = extract_html(text, builder)
        elif media == "markdown":
            title = extract_markdown(text, builder)
        else:
            title = extract_text(text, builder)
    full_text = builder.finish()
    if not title:
        first_heading = next((b for b in builder.blocks if b.kind == "heading"), None)
        title = first_heading.text if first_heading else None
    if not builder.blocks:
        warnings.append("The subject appears to be empty.")
    return SubjectDocument(
        source_name=PurePath(filename).name or filename,
        media_type=media,
        title=re.sub(r"\s+", " ", title).strip() if title else None,
        text=full_text,
        blocks=builder.blocks,
        sha256=hashlib.sha256(data).hexdigest(),
        warnings=warnings,
    )
