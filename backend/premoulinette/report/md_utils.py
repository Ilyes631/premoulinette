"""Markdown primitives that stay safe with untrusted text (student output, file names...).

Inline text is backslash-escaped (CommonMark allows escaping any ASCII punctuation), so raw HTML such
as ``<script>`` is never interpreted by a renderer. Code spans and fences pick a delimiter longer than
any backtick run inside the content.
"""
from __future__ import annotations

import re

_SPECIAL = re.compile(r"([\\`*\[\]<>|&#~])")
_LOOSE_UNDERSCORE = re.compile(r"(?<![0-9A-Za-z])_|_(?![0-9A-Za-z])")  # intraword `_` is harmless
_BACKTICKS = re.compile(r"`+")


def md_text(text: str) -> str:
    """Escape inline Markdown/HTML and flatten line breaks (safe inside table cells and headings)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPECIAL.sub(r"\\\1", text)
    text = _LOOSE_UNDERSCORE.sub(r"\\_", text)
    return text.replace("\n", " ↵ ")


def md_code(text: str, *, table: bool = False) -> str:
    """Inline code span holding ``text`` verbatim (line breaks shown as ↵/␍)."""
    if text == "":
        return "*(empty)*"
    text = text.replace("\r", "␍").replace("\n", "↵")
    if table:
        text = text.replace("|", "\\|")  # GFM tables split on `|` even inside code spans
    longest = max((len(run) for run in _BACKTICKS.findall(text)), default=0)
    delim = "`" * (longest + 1)
    pad = text[0] == "`" or text[-1] == "`" or (text[0] == " " and text[-1] == " " and text.strip() != "")
    if pad:
        text = f" {text} "
    return f"{delim}{text}{delim}"


def md_fence(body: str, lang: str = "") -> str:
    longest = max((len(run) for run in _BACKTICKS.findall(body)), default=0)
    fence = "`" * max(3, longest + 1)
    if not body.endswith("\n"):
        body += "\n"
    return f"{fence}{lang}\n{body}{fence}"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Cells must already be escaped (md_text / md_code(table=True))."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


class MarkdownWriter:
    """Accumulates blocks separated by blank lines."""

    def __init__(self) -> None:
        self._blocks: list[str] = []

    def heading(self, level: int, text: str) -> None:
        self._blocks.append(f"{'#' * level} {text}")

    def block(self, text: str) -> None:
        if text:
            self._blocks.append(text)

    def bullets(self, items: list[str]) -> None:
        if items:
            self._blocks.append("\n".join(f"- {item}" for item in items))

    def render(self) -> str:
        return "\n\n".join(self._blocks).rstrip() + "\n"
