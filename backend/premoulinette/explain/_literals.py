"""Locate string literals on one source line and compute an in-place text correction.

Used by the fix builders for typos in returned strings, prompts and printed text. The rule is strict:
the differing region of the runtime text must fall inside exactly one *static* part of exactly one
literal on the line (f-string fields excluded), otherwise no fix is proposed.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass

from premoulinette.explain._markdown import diff_region

_PREFIXES = {"", "r", "u", "b", "br", "rb", "f", "fr", "rf", "t", "tr", "rt"}


@dataclass(frozen=True)
class Chunk:
    start: int          # source span inside the line
    end: int
    value: str          # decoded runtime text of a static part ("" for fields)
    is_field: bool
    mappable: bool      # source text == runtime text (no escapes), so it can be edited in place


@dataclass(frozen=True)
class Literal:
    start: int          # whole literal, prefix and quotes included
    end: int
    prefix: str
    quote: str
    chunks: tuple[Chunk, ...]

    @property
    def kind(self) -> str:
        p = self.prefix.lower()
        if "b" in p:
            return "bytes"
        if "t" in p:
            return "template"
        return "fstring" if "f" in p else "str"

    @property
    def decoded(self) -> str | None:
        """Full value of a plain literal (None for f-strings / bytes)."""
        if self.kind != "str":
            return None
        return "".join(ch.value for ch in self.chunks)


def _skip_simple_string(line: str, pos: int) -> int | None:
    """Index just after a quoted string nested in an f-string field starting at ``pos``."""
    quote = line[pos]
    k = pos + 1
    while k < len(line):
        if line[k] == "\\":
            k += 2
            continue
        if line[k] == quote:
            return k + 1
        k += 1
    return None


def _decode(prefix: str, quote: str, text: str) -> str | None:
    """Runtime value of a static source fragment (handles escapes)."""
    try:
        value = ast.literal_eval(prefix.replace("f", "").replace("F", "") + quote + text + quote)
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, str) else None


def _static_chunk(line: str, start: int, end: int, prefix: str, quote: str, is_f: bool) -> Chunk | None:
    src = line[start:end]
    escaped = "\\" in src or (is_f and ("{{" in src or "}}" in src))
    if not escaped:
        return Chunk(start, end, src, False, True)
    text = src.replace("{{", "{").replace("}}", "}") if is_f else src
    value = _decode(prefix, quote, text)
    if value is None:
        return None
    return Chunk(start, end, value, False, False)


def _scan_body(line: str, start: int, body_start: int, prefix: str, quote: str) -> Literal | None:
    is_f = "f" in prefix.lower() or "t" in prefix.lower()
    chunks: list[Chunk] = []
    k = chunk_start = body_start
    depth = 0
    field_start = 0
    while k < len(line):
        if depth == 0 and line.startswith(quote, k):
            if k > chunk_start:
                chunk = _static_chunk(line, chunk_start, k, prefix, quote, is_f)
                if chunk is None:
                    return None
                chunks.append(chunk)
            return Literal(start, k + len(quote), prefix, quote, tuple(chunks))
        ch = line[k]
        if depth == 0:
            if ch == "\\":
                k += 2
                continue
            if is_f and (line.startswith("{{", k) or line.startswith("}}", k)):
                k += 2
                continue
            if is_f and ch == "{":
                if k > chunk_start:
                    chunk = _static_chunk(line, chunk_start, k, prefix, quote, is_f)
                    if chunk is None:
                        return None
                    chunks.append(chunk)
                depth, field_start = 1, k
            k += 1
            continue
        if ch in "'\"":
            after = _skip_simple_string(line, k)
            if after is None:
                return None
            k = after
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunks.append(Chunk(field_start, k + 1, "", True, False))
                chunk_start = k + 1
        k += 1
    return None  # unterminated on this line (multi-line literal)


def scan_line(line: str) -> list[Literal] | None:
    """String literals that start and end on ``line``; None if one spans several lines."""
    literals: list[Literal] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "#":
            break
        if ch not in "'\"":
            i += 1
            continue
        j = i
        while j > 0 and line[j - 1].isalpha():
            j -= 1
        prefix = line[j:i]
        if prefix.lower() not in _PREFIXES or (j > 0 and (line[j - 1].isalnum() or line[j - 1] == "_")):
            j, prefix = i, ""
        quote = line[i:i + 3] if line[i:i + 3] in ('"""', "'''") else ch
        literal = _scan_body(line, j, i + len(quote), prefix, quote)
        if literal is None:
            return None
        literals.append(literal)
        i = literal.end
    return literals


def _can_hold(literal: Literal, text: str) -> bool:
    """True if ``text`` can be written verbatim inside the literal (no escaping needed)."""
    if any(ch in text for ch in "\\\n\r"):
        return False
    if literal.kind == "fstring" and ("{" in text or "}" in text):
        return False
    if len(literal.quote) == 1:
        return literal.quote not in text
    return literal.quote not in text and not text.endswith(literal.quote[0])


@dataclass(frozen=True)
class TextEdit:
    start: int
    end: int
    new_text: str

    def apply(self, line: str) -> str:
        return line[: self.start] + self.new_text + line[self.end:]


def find_text_edit(line: str, actual: str, expected: str) -> TextEdit | None:
    """In-place edit of a string literal on ``line`` turning the runtime text ``actual`` into ``expected``.

    Returns None when the line has no literal producing the differing region, or when more than one
    literal part could be responsible (ambiguous), or when the new text would need escaping.
    """
    if actual == expected:
        return None
    literals = scan_line(line)
    if not literals:
        return None
    start, actual_end, expected_end = diff_region(expected, actual)
    replacement = expected[start:expected_end]
    candidates: list[tuple[Literal, Chunk, int]] = []
    for literal in literals:
        if literal.kind in ("bytes", "template"):
            continue
        for chunk in literal.chunks:
            if chunk.is_field or not chunk.value:
                continue
            size = len(chunk.value)
            pos = actual.find(chunk.value)
            while pos != -1:
                if pos <= start and actual_end <= pos + size:
                    candidates.append((literal, chunk, pos))
                pos = actual.find(chunk.value, pos + 1)
    if len(candidates) != 1:
        return None
    literal, chunk, pos = candidates[0]
    if not chunk.mappable:
        return None
    new_value = actual[pos:start] + replacement + actual[actual_end:pos + len(chunk.value)]
    if not _can_hold(literal, new_value):
        return None
    return TextEdit(chunk.start, chunk.end, new_value)
