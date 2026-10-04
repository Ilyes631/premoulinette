"""Whitespace/quote/arrow-insensitive search in the subject text, with positions mapped back to lines.

Grounding needs to answer "is this literally in the subject?" while tolerating cosmetic differences:
``f(1,2)`` vs ``f(1, 2)``, ``'x'`` vs ``"x"``, ``→`` vs ``->`` and HTML entities. Both the haystack and
the needles are reduced to a *compact* form (no whitespace, unified quotes and arrows); every compact
character remembers its offset in the original text so a match can be turned into a line and an excerpt.
"""
from __future__ import annotations

import html

_QUOTES = frozenset("'\"‘’‚‛“”„‟«»′″")
_ARROWS = frozenset("→⟶⇒➜➔⟹")
_DROPPED = frozenset("`​‌‍﻿")
_MINUS = frozenset("−–")


def _map_char(ch: str) -> str:
    if ch.isspace() or ch in _DROPPED:
        return ""
    if ch in _QUOTES:
        return "'"
    if ch in _ARROWS:
        return "->"
    if ch in _MINUS:
        return "-"
    if ch == "…":
        return "..."
    return ch


def compact(text: str) -> str:
    """Compact form of a needle (entities decoded, whitespace removed, quotes/arrows unified)."""
    text = html.unescape(text).replace("=>", "->")
    return "".join(_map_char(ch) for ch in text)


class TextIndex:
    def __init__(self, text: str) -> None:
        self.text = text
        source = text.replace("=>", "->")      # same length: offsets stay valid
        chars: list[str] = []
        origin: list[int] = []
        for i, ch in enumerate(source):
            for c in _map_char(ch):
                chars.append(c)
                origin.append(i)
        self.compact = "".join(chars)
        self.lower = self.compact.lower()
        self._origin = origin

    def find(self, needle: str, start: int = 0, end: int | None = None) -> int:
        """Compact index of the first match of ``needle`` (already compacted or not), or -1."""
        n = compact(needle)
        if not n:
            return -1
        return self.compact.find(n, max(0, start), len(self.compact) if end is None else end)

    def find_all(self, needle: str, limit: int = 50) -> list[int]:
        n = compact(needle)
        out: list[int] = []
        if not n:
            return out
        pos = self.compact.find(n)
        while pos >= 0 and len(out) < limit:
            out.append(pos)
            pos = self.compact.find(n, pos + 1)
        return out

    def _bounded(self, compact_index: int, n: str) -> bool:
        """True if the match does not cut a word/number of the ORIGINAL text in two
        (``exec`` inside ``execute``, ``273`` inside ``273.15``, ``15`` inside ``273.15``)."""
        start = self.offset(compact_index)
        end = self.offset(compact_index + len(n) - 1) + 1
        text = self.text
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        after2 = text[end + 1] if end + 1 < len(text) else ""

        def word(c: str) -> bool:
            return bool(c) and (c.isalnum() or c == "_")

        if word(n[0]) and word(before):
            return False
        if n[0].isdigit() and before == "." and start > 1 and text[start - 2].isdigit():
            return False
        if word(n[-1]) and word(after):
            return False
        if n[-1].isdigit() and after == "." and after2.isdigit():
            return False
        return True

    def find_bounded(self, needle: str, start: int = 0, end: int | None = None) -> int:
        """Like :meth:`find`, but the match must not start/end in the middle of a word or number."""
        n = compact(needle)
        if not n:
            return -1
        stop = len(self.compact) if end is None else end
        pos = self.compact.find(n, max(0, start), stop)
        while pos >= 0:
            if self._bounded(pos, n):
                return pos
            pos = self.compact.find(n, pos + 1, stop)
        return -1

    def find_all_bounded(self, needle: str, limit: int = 50) -> list[int]:
        n = compact(needle)
        return [p for p in self.find_all(needle, limit) if self._bounded(p, n)] if n else []

    def contains_word(self, word: str) -> bool:
        """Case-sensitive identifier lookup (whole word: ``exec`` does not match ``execute``)."""
        return bool(word) and self.find_bounded(word) >= 0

    def offset(self, compact_index: int) -> int:
        if not self._origin:
            return 0
        return self._origin[max(0, min(compact_index, len(self._origin) - 1))]

    def line_of(self, compact_index: int) -> int:
        return self.text.count("\n", 0, self.offset(compact_index)) + 1

    def excerpt(self, compact_index: int, needle: str, limit: int = 300) -> str:
        """The original line(s) covering a match."""
        n = len(compact(needle)) or 1
        start = self.offset(compact_index)
        end = self.offset(compact_index + n - 1) + 1
        line_start = self.text.rfind("\n", 0, start) + 1
        line_end = self.text.find("\n", end)
        snippet = self.text[line_start: len(self.text) if line_end < 0 else line_end].strip()
        return snippet if len(snippet) <= limit else snippet[: limit - 1] + "…"
