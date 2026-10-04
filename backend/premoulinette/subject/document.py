"""Extracted subject document: typed blocks in document order + the full plain text.

Produced by :mod:`premoulinette.subject.extract`, consumed by the heuristic parser, the AI parser
(``text``) and grounding. Positions (``Block.line``) refer to ``SubjectDocument.text``.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlockKind = Literal["heading", "paragraph", "code", "list_item", "table_row"]
MediaType = Literal["html", "markdown", "text", "pdf"]


class Block(BaseModel):
    kind: BlockKind
    text: str                                   # plain text; for code: exact content (no HTML entities)
    level: int | None = None                    # heading level 1..6
    lang: str | None = None                     # code: "python", "terminal", None...
    inputs: list[tuple[int, int]] = Field(default_factory=list)   # code: (start, end) user-input spans
    inline_code: list[str] = Field(default_factory=list)          # paragraph/list_item: inline code, in order
    section: str = ""                           # heading path, e.g. "Exercise 2 — Safe speed"
    line: int = 0                               # 1-based line in SubjectDocument.text

    def input_texts(self) -> list[str]:
        return [self.text[s:e] for s, e in self.inputs]


class SubjectDocument(BaseModel):
    source_name: str
    media_type: MediaType
    title: str | None
    text: str
    blocks: list[Block]
    sha256: str
    warnings: list[str] = Field(default_factory=list)

    def headings(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "heading"]

    def code_blocks(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "code"]
