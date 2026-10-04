"""Small text helpers shared by the extractors and the heuristic parser."""
from __future__ import annotations

import re
from dataclasses import dataclass

_WS_RE = re.compile(r"\s+")
PLACEHOLDER_RE = re.compile(r"⟦(\d+)⟧")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'(⟦A-ZÀ-Ý0-9])|\n+(?=\s*[-*•]\s)")

EXCERPT_MAX = 300


def collapse_ws(text: str) -> str:
    """Collapse every whitespace run (including newlines and NBSP) into one space and strip."""
    return _WS_RE.sub(" ", text).strip()


def excerpt(text: str, limit: int = EXCERPT_MAX) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def decode_bytes(data: bytes) -> tuple[str, list[str]]:
    """Decode subject bytes: UTF-8 (with/without BOM), UTF-16 with BOM, cp1252 fallback.

    Newlines are normalized to ``\\n``.
    """
    warnings: list[str] = []
    text: str
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("cp1252")
                warnings.append("Subject is not valid UTF-8; decoded as Windows-1252.")
            except UnicodeDecodeError:
                text = data.decode("cp1252", errors="replace")
                warnings.append("Subject is not valid UTF-8; decoded as Windows-1252 with replacement characters.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text, warnings


def split_backticks(line: str) -> tuple[str, list[str]]:
    """Remove `inline code` markers from a plain-text line; return (text, codes)."""
    codes: list[str] = []

    def repl(m: re.Match[str]) -> str:
        codes.append(m.group(1))
        return m.group(1)

    return re.sub(r"`([^`\n]+)`", repl, line), codes


@dataclass(frozen=True)
class Marked:
    """Block text where every located inline code span is replaced by a ``⟦i⟧`` placeholder."""

    text: str
    codes: tuple[str, ...]

    def unmark(self, fragment: str) -> str:
        return PLACEHOLDER_RE.sub(lambda m: self.codes[int(m.group(1))], fragment)

    def single_code(self, fragment: str) -> str | None:
        """If ``fragment`` is exactly one placeholder (modulo spaces), return its code."""
        m = PLACEHOLDER_RE.fullmatch(fragment.strip())
        return self.codes[int(m.group(1))] if m else None


def _find_code(text: str, code: str, start: int) -> tuple[int, int]:
    for candidate in (code, code.strip(), collapse_ws(code)):
        if not candidate:
            continue
        idx = text.find(candidate, start)
        if idx >= 0:
            return idx, len(candidate)
    return -1, 0


def mark(text: str, inline_code: list[str]) -> Marked:
    """Replace inline code occurrences (searched in order) by placeholders."""
    text = text.replace("⟦", "[").replace("⟧", "]")
    out: list[str] = []
    codes: list[str] = []
    pos = 0
    for code in inline_code:
        idx, length = _find_code(text, code, pos)
        if idx < 0:
            continue
        out.append(text[pos:idx])
        out.append(f"⟦{len(codes)}⟧")
        codes.append(code)
        pos = idx + length
    out.append(text[pos:])
    return Marked("".join(out), tuple(codes))


def sentences(marked_text: str) -> list[str]:
    """Split a (marked) paragraph into sentences; newlines inside sentences become spaces."""
    parts = _SENTENCE_SPLIT_RE.split(marked_text)
    return [p.replace("\n", " ").strip() for p in parts if p.strip()]


def strip_call_parens(name: str) -> str:
    """``"abs()"`` -> ``"abs"``, ``".sort()"`` -> ``"sort"``, ``"str.split"`` -> ``"split"``."""
    name = name.strip().strip("`").strip()
    name = re.sub(r"\(.*\)\s*$", "", name).strip()
    if "." in name:
        name = name.rsplit(".", 1)[1]
    return name


IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def is_identifier(name: str) -> bool:
    return bool(IDENT_RE.fullmatch(name))
