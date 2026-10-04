"""Markdown subject extraction (markdown-it-py tokens)."""
from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token

from premoulinette.subject.codelang import detect_code_lang
from premoulinette.subject.docbuilder import DocBuilder
from premoulinette.subject.extract_html import extract_html


def _normalize_lines(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _render_inline(token: Token) -> tuple[str, list[str]]:
    pieces: list[str] = []
    codes: list[str] = []
    for child in token.children or []:
        if child.type == "text":
            pieces.append(child.content)
        elif child.type == "code_inline":
            pieces.append(child.content)
            codes.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            pieces.append("\n")
        elif child.type == "html_inline" and child.content.lower().startswith("<br"):
            pieces.append("\n")
        elif child.type == "image":
            pieces.append(child.content)
    return _normalize_lines("".join(pieces)), codes


class _MdState:
    def __init__(self, builder: DocBuilder) -> None:
        self.b = builder
        self.heading_level: int | None = None
        self.li_stack: list[tuple[list[str], list[str]]] = []   # (texts, codes) per open list item
        self.row: list[str] | None = None
        self.row_codes: list[str] = []
        self.in_cell = False

    def flush_li(self) -> None:
        if self.li_stack:
            texts, codes = self.li_stack[-1]
            if texts:
                self.b.list_item("\n".join(texts), list(codes))
            texts.clear()
            codes.clear()

    def inline(self, token: Token) -> None:
        text, codes = _render_inline(token)
        if self.heading_level is not None:
            self.b.heading(text, self.heading_level)
        elif self.in_cell and self.row is not None:
            self.row.append(" ".join(text.split()))
            self.row_codes += codes
        elif self.li_stack:
            texts, li_codes = self.li_stack[-1]
            if text:
                texts.append(text)
            li_codes += codes
        else:
            self.b.paragraph(text, codes)

    def code(self, content: str, info: str) -> None:
        self.flush_li()
        declared = info.strip().split()[0] if info.strip() else None
        self.b.code(content, detect_code_lang(declared, content))

    def handle(self, tok: Token) -> None:
        t = tok.type
        if t == "heading_open":
            self.heading_level = int(tok.tag[1:])
        elif t == "heading_close":
            self.heading_level = None
        elif t == "inline":
            self.inline(tok)
        elif t == "list_item_open":
            self.li_stack.append(([], []))
        elif t == "list_item_close":
            self.flush_li()
            self.li_stack.pop()
        elif t in ("bullet_list_open", "ordered_list_open"):
            self.flush_li()
        elif t == "fence":
            self.code(tok.content, tok.info)
        elif t == "code_block":
            self.code(tok.content, "")
        elif t == "html_block":
            self.flush_li()
            extract_html(tok.content, self.b)
        elif t == "tr_open":
            self.row, self.row_codes = [], []
        elif t in ("th_open", "td_open"):
            self.in_cell = True
        elif t in ("th_close", "td_close"):
            self.in_cell = False
        elif t == "tr_close" and self.row is not None:
            self.b.table_row(" | ".join(self.row), self.row_codes)
            self.row = None


def extract_markdown(text: str, builder: DocBuilder) -> str | None:
    """Append the blocks of a Markdown document to ``builder``; return the first h1 text (title)."""
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    state = _MdState(builder)
    title: str | None = None
    start = len(builder.blocks)
    for tok in md.parse(text):
        state.handle(tok)
    for block in builder.blocks[start:]:
        if block.kind == "heading" and block.level == 1:
            title = block.text
            break
    return title
