"""Plain-text (and PDF-extracted text) segmentation into blocks.

Line based: blank lines separate paragraphs; runs of code-looking lines (doctests, shell sessions,
``def`` signatures, directory trees, ``f(x) -> y`` examples, indented code) become code blocks;
title-looking lines ("Exercise 2 — x", "Exercice 2", "# Title", "1.2 Title", ALL CAPS) become headings.
"""
from __future__ import annotations

import re
import textwrap

from premoulinette.subject.codelang import detect_code_lang
from premoulinette.subject.docbuilder import DocBuilder
from premoulinette.subject.textutil import split_backticks
from premoulinette.subject.transcript import match_prompt

TREE_CHARS = ("├", "└", "│", "|--", "`--", "+--", "|__")
_TREE_PREFIX_RE = re.compile(r"^[\s│|├└┬┼─`+\-]*")
_PATH_RE = re.compile(r"[\w.\-+@~]+(?:/[\w.\-+@~]+)*/?")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*#*\s*$")
_KEYWORD_HEADING_RE = re.compile(
    r"(?i)^(?:exercises?|exercices?|exo\b|ex\s*\d|part(?:ie)?\b|bonus|section|chap(?:ter|itre)|step|[ée]tape|task|t[âa]che|"
    r"problem|probl[èe]me|rules|r[èe]gles|consignes|submission|rendu|structure|architecture|introduction|instructions|"
    r"objectifs?|goals?|optional|facultatif|annexe|appendix|prerequisites|pr[ée]requis)\b"
)
_BONUS_NUMBERED_RE = re.compile(r"(?i)^(?:bonus|optional|optionnel|facultatif)\s*\d")
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+[A-ZÀ-Ý]")
_ROMAN_HEADING_RE = re.compile(r"^[IVX]+[.)]\s+[A-ZÀ-Ý]")
_UNDERLINE_RE = re.compile(r"^\s*(=+|-+)\s*$")
_BULLET_RE = re.compile(r"^(\s*)(?:[-*•+]|\d+[.)])\s+(.*)$")
_DEF_RE = re.compile(r"^\s*(?:def|class)\s+\w+")
_EXAMPLE_LINE_RE = re.compile(r"^\s*(?:print\()?[A-Za-z_]\w*\(.*\)\)?\s*(?:->|→|==|=>)\s*\S")
_HARD_STOP_RE = re.compile(r"(?i)^\s*(?:exercises?|exercices?|bonus|part(?:ie)?)\s*\d")


def _blank(line: str) -> bool:
    return not line.strip()


def _has_tree_chars(line: str) -> bool:
    return any(c in line for c in TREE_CHARS)


def path_like(line: str) -> bool:
    name = _TREE_PREFIX_RE.sub("", line).strip()
    name = re.split(r"\s{2,}|\s#|\s<-|\s←", name)[0].strip()
    if not name or not _PATH_RE.fullmatch(name):
        return False
    return name.endswith("/") or "/" in name or bool(re.search(r"\.\w+$", name))


def heading_level(line: str) -> int | None:
    s = line.strip()
    if not s or len(s) > 90:
        return None
    m = _MD_HEADING_RE.match(s)
    if m:
        return len(m.group(1))
    if s[-1] in ".:;,!" or "`" in s or "(" in s:
        return None
    words = len(s.split())
    if _KEYWORD_HEADING_RE.match(s) and words <= 12:
        return 3 if _BONUS_NUMBERED_RE.match(s) else 2
    m = _NUMBERED_HEADING_RE.match(s)
    if m and words <= 7:
        return min(6, 2 + m.group(1).count("."))
    if _ROMAN_HEADING_RE.match(s) and words <= 7:
        return 2
    letters = [c for c in s if c.isalpha()]
    if len(letters) >= 3 and s.upper() == s and len(s) <= 60 and words <= 8:
        return 2
    return None


def heading_text(line: str) -> str:
    m = _MD_HEADING_RE.match(line.strip())
    return m.group(2) if m else line.strip()


def _code_start_kind(lines: list[str], i: int) -> str | None:
    line = lines[i]
    s = line.lstrip()
    if s.startswith(">>>"):
        return "doctest"
    if match_prompt(line) is not None:
        return "session"
    if _DEF_RE.match(line):
        return "def"
    if _has_tree_chars(line):
        return "tree"
    if path_like(line) and i + 1 < len(lines) and _has_tree_chars(lines[i + 1]):
        return "tree"
    if _EXAMPLE_LINE_RE.match(line) and not s.startswith("def "):
        return "example"
    if line.startswith(("    ", "\t")):
        return "indent"
    return None


def _consume_code(lines: list[str], i: int, kind: str) -> int:
    n = len(lines)
    j = i + 1
    if kind in ("doctest", "session"):
        while j < n and not _blank(lines[j]) and not _HARD_STOP_RE.match(lines[j]):
            j += 1
    elif kind == "def":
        while j < n and not _blank(lines[j]):
            nxt = lines[j]
            if nxt.startswith((" ", "\t")) or _code_start_kind(lines, j) in ("def", "doctest", "example"):
                j += 1
            else:
                break
    elif kind == "tree":
        while j < n and not _blank(lines[j]) and (_has_tree_chars(lines[j]) or path_like(lines[j])):
            j += 1
    elif kind == "example":
        while j < n and _EXAMPLE_LINE_RE.match(lines[j]):
            j += 1
    else:  # indent
        while j < n and not _blank(lines[j]) and lines[j].startswith((" ", "\t")):
            j += 1
    return j


class _TextSegmenter:
    def __init__(self, builder: DocBuilder) -> None:
        self.b = builder
        self.para: list[str] = []

    def flush(self) -> None:
        if not self.para:
            return
        texts, codes = [], []
        for line in self.para:
            t, c = split_backticks(" ".join(line.split()))
            texts.append(t)
            codes += c
        self.para = []
        self.b.paragraph("\n".join(texts), codes)

    def run(self, text: str) -> str | None:
        lines = text.split("\n")
        n = len(lines)
        i = 0
        title: str | None = None
        while i < n:
            line = lines[i]
            if _blank(line):
                self.flush()
                i += 1
                continue
            kind = _code_start_kind(lines, i)
            if title is None and not kind and len(line.strip()) <= 100:
                title = heading_text(line)
                self.b.heading(title, 1)
                i += 1
                continue
            if (not kind and i + 1 < n and _UNDERLINE_RE.match(lines[i + 1])
                    and len(line.strip()) <= 80 and not self.para):
                self.flush()
                self.b.heading(line, 1 if "=" in lines[i + 1] else 2)
                i += 2
                continue
            level = None if kind else heading_level(line)
            if level:
                self.flush()
                self.b.heading(heading_text(line), level)
                i += 1
                continue
            if kind and not (kind == "indent" and self.para):
                self.flush()
                j = _consume_code(lines, i, kind)
                # Dedent every kind: an indented shell session or doctest must not keep the
                # document's indentation in its expected output / prompts.
                code = textwrap.dedent("\n".join(lines[i:j]) + "\n")
                self.b.code(code, detect_code_lang(None, code))
                i = j
                continue
            m = _BULLET_RE.match(line)
            if m:
                self.flush()
                i = self._bullet(lines, i, m)
                continue
            self.para.append(line.strip())
            i += 1
        self.flush()
        return title

    def _bullet(self, lines: list[str], i: int, m: re.Match[str]) -> int:
        indent = len(m.group(1))
        parts = [m.group(2).strip()]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if _blank(nxt) or _BULLET_RE.match(nxt) or heading_level(nxt) or _code_start_kind(lines, j) not in (None, "indent"):
                break
            if len(nxt) - len(nxt.lstrip()) <= indent:
                break
            parts.append(nxt.strip())
            j += 1
        text, codes = split_backticks(" ".join(" ".join(parts).split()))
        self.b.list_item(text, codes)
        return j


def extract_text(text: str, builder: DocBuilder) -> str | None:
    """Append the blocks of a plain-text document; return the detected title (first short line)."""
    return _TextSegmenter(builder).run(text)
