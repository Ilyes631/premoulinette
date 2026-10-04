"""Source text helpers: line splitting consistent with Python's tokenizer and code excerpts."""
from __future__ import annotations

import re

from premoulinette.results.models import CodeExcerpt

_NEWLINE = re.compile(r"\r\n|\r|\n")
MAX_EXCERPT_LINES = 25


def split_lines(text: str) -> list[str]:
    """Split on ``\\r\\n``, ``\\r`` and ``\\n`` only.

    ``str.splitlines`` also splits on form feeds and Unicode separators, which Python's tokenizer
    does not, and would shift every line number after such a character.
    """
    if not text:
        return []
    lines = _NEWLINE.split(text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def make_excerpt(
    source: str | None,
    file: str,
    line: int | None,
    end_line: int | None = None,
    *,
    context: int = 2,
) -> CodeExcerpt | None:
    """Lines ``line - context .. end_line + context`` of ``source`` (1-based), highlighting the range."""
    if source is None or not line or line < 1:
        return None
    lines = split_lines(source)
    if line > len(lines):
        return None
    last = min(max(end_line or line, line), len(lines))
    last = min(last, line + MAX_EXCERPT_LINES - 2 * context - 1)
    start = max(1, line - context)
    stop = min(len(lines), last + context)
    return CodeExcerpt(
        file=file,
        start_line=start,
        lines=lines[start - 1:stop],
        highlight=list(range(line, last + 1)),
    )
