"""Accumulates blocks in document order, then computes ``SubjectDocument.text``, lines and sections."""
from __future__ import annotations

from premoulinette.subject.document import Block
from premoulinette.subject.textutil import collapse_ws

_TIGHT_KINDS = {"list_item", "table_row"}


class DocBuilder:
    def __init__(self) -> None:
        self.blocks: list[Block] = []

    # ---- adders -------------------------------------------------------------------------------
    def heading(self, text: str, level: int) -> None:
        text = collapse_ws(text)
        if text:
            self.blocks.append(Block(kind="heading", text=text, level=max(1, min(6, level))))

    def paragraph(self, text: str, inline_code: list[str] | None = None) -> None:
        text = text.strip()
        if text:
            self.blocks.append(Block(kind="paragraph", text=text, inline_code=list(inline_code or [])))

    def list_item(self, text: str, inline_code: list[str] | None = None) -> None:
        text = text.strip()
        if text:
            self.blocks.append(Block(kind="list_item", text=text, inline_code=list(inline_code or [])))

    def table_row(self, text: str, inline_code: list[str] | None = None) -> None:
        text = text.strip()
        if text.strip(" |"):
            self.blocks.append(Block(kind="table_row", text=text, inline_code=list(inline_code or [])))

    def code(self, text: str, lang: str | None, inputs: list[tuple[int, int]] | None = None) -> None:
        if text.strip():
            self.blocks.append(Block(kind="code", text=text, lang=lang, inputs=list(inputs or [])))

    # ---- finish -------------------------------------------------------------------------------
    def finish(self) -> str:
        """Set ``line`` and ``section`` on every block and return the full document text."""
        self._assign_sections()
        parts: list[str] = []
        line = 1
        prev: Block | None = None
        for block in self.blocks:
            if prev is not None:
                sep = "\n" if (block.kind == prev.kind and block.kind in _TIGHT_KINDS) else "\n\n"
                parts.append(sep)
                line += sep.count("\n")
            block.line = line
            rendered = self._render(block)
            parts.append(rendered)
            line += rendered.count("\n")
            prev = block
        return "".join(parts) + ("\n" if parts else "")

    @staticmethod
    def _render(block: Block) -> str:
        if block.kind == "code":
            return block.text.rstrip("\n")
        if block.kind == "list_item":
            return "- " + block.text
        return block.text

    def _assign_sections(self) -> None:
        headings = [b for b in self.blocks if b.kind == "heading"]
        h1_count = sum(1 for h in headings if h.level == 1)
        # A single leading h1 is the document title: it is not part of section paths.
        skip_title = bool(headings) and headings[0].level == 1 and h1_count == 1
        stack: list[tuple[int, str]] = []
        first_heading_seen = False
        for block in self.blocks:
            if block.kind == "heading":
                is_title = skip_title and not first_heading_seen
                first_heading_seen = True
                if is_title:
                    block.section = block.text
                    continue
                level = block.level or 1
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, block.text))
            block.section = " > ".join(t for _, t in stack)
