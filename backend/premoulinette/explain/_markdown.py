"""Deterministic Markdown helpers for explanations (code spans, fences, caret diffs, visible whitespace)."""
from __future__ import annotations

import ast
import difflib
import json
import re

INVISIBLE = {" ": "␠", "\t": "→", "\r": "␍", "\n": "↵"}
_TRAILING_WS = re.compile(r"[ \t]+$")
_MAX_DIFF_WIDTH = 100


def join(*parts: str | None) -> str:
    """Join non-empty paragraphs with a blank line."""
    return "\n\n".join(p.strip("\n") for p in parts if p and p.strip())


def code(text: str) -> str:
    """Inline code span that survives backticks; line breaks are shown as visible symbols."""
    text = text.replace("\r", INVISIBLE["\r"]).replace("\n", INVISIBLE["\n"])
    if not text:
        return "` `"
    runs = re.findall(r"`+", text)
    if not runs:
        return f"`{text}`"
    fence = "`" * (max(len(r) for r in runs) + 1)
    return f"{fence} {text} {fence}"


def block(text: str, lang: str = "") -> str:
    """Fenced code block whose fence is longer than any backtick run inside ``text``."""
    runs = re.findall(r"`{3,}", text)
    fence = "`" * max(3, max((len(r) for r in runs), default=0) + 1)
    body = text[:-1] if text.endswith("\n") else text
    return f"{fence}{lang}\n{body}\n{fence}"


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def numbered(items: list[str]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate((x for x in items if x), start=1))


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def show_ws(text: str) -> str:
    """Make every whitespace character visible (1 char -> 1 char, so carets stay aligned)."""
    return "".join(INVISIBLE.get(ch, ch) for ch in text)


def show_trailing(text: str) -> str:
    """Make only trailing spaces/tabs visible (e.g. the space at the end of a prompt)."""
    m = _TRAILING_WS.search(text)
    if not m:
        return text
    return text[: m.start()] + show_ws(m.group(0))


def display_value(repr_src: str, type_name: str | None = None) -> str:
    """Python value as a student would write it: strings in double quotes, other values as repr."""
    if type_name in (None, "str"):
        try:
            value = ast.literal_eval(repr_src)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            return repr_src
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
    return repr_src


def str_literal(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def truncate(text: str, limit: int = 600) -> str:
    return text if len(text) <= limit else text[:limit] + " …"


def tail_lines(text: str, count: int) -> str:
    lines = text.rstrip("\n").splitlines()
    if len(lines) <= count:
        return "\n".join(lines)
    return "\n".join(["…", *lines[-count:]])


# ---------------------------------------------------------------------------------------------
# Character-level differences
# ---------------------------------------------------------------------------------------------


def diff_region(expected: str, actual: str) -> tuple[int, int, int]:
    """Minimal differing region: ``(start, actual_end, expected_end)`` after common prefix/suffix."""
    shortest = min(len(expected), len(actual))
    start = 0
    while start < shortest and expected[start] == actual[start]:
        start += 1
    suffix = 0
    while suffix < shortest - start and expected[-1 - suffix] == actual[-1 - suffix]:
        suffix += 1
    return start, len(actual) - suffix, len(expected) - suffix


def _opcodes(expected: str, actual: str) -> list[tuple[str, int, int, int, int]]:
    return [op for op in difflib.SequenceMatcher(None, expected, actual, autojunk=False).get_opcodes() if op[0] != "equal"]


def involves_whitespace(expected: str, actual: str) -> bool:
    """True when at least one differing segment contains a space, tab or line break."""
    for _, i1, i2, j1, j2 in _opcodes(expected, actual):
        if any(ch in INVISIBLE for ch in expected[i1:i2] + actual[j1:j2]):
            return True
    return False


def caret_diff(expected: str, actual: str, labels: tuple[str, str]) -> str:
    """Code block with the expected and received text and a ``^`` line under every difference."""
    marks: set[int] = set()
    for _, _, _, j1, j2 in _opcodes(expected, actual):
        marks.update(range(j1, j2) if j2 > j1 else (j1,))
    exp_v, act_v = show_ws(expected), show_ws(actual)
    carets = "".join("^" if i in marks else " " for i in range(len(actual) + 1)).rstrip()
    longest = max(len(exp_v), len(act_v), len(carets))
    if longest > _MAX_DIFF_WIDTH and marks:
        start = max(0, min(marks) - 30)
        end = start + _MAX_DIFF_WIDTH
        lead = "…" if start else ""
        exp_v, act_v = lead + exp_v[start:end], lead + act_v[start:end]
        carets = (" " if start else "") + carets[start:end]
    width = max(len(label) for label in labels)
    lines = [
        f"{labels[0].ljust(width)} {exp_v}",
        f"{labels[1].ljust(width)} {act_v}",
        f"{' ' * width} {carets}".rstrip(),
    ]
    return block("\n".join(lines), "text")
