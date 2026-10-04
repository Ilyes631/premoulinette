"""HTML subject extraction (BeautifulSoup, html.parser)."""
from __future__ import annotations

from bs4 import BeautifulSoup
from bs4.element import CData, Comment, Declaration, Doctype, NavigableString, ProcessingInstruction, Tag

from premoulinette.subject.codelang import detect_code_lang, lang_from_classes
from premoulinette.subject.docbuilder import DocBuilder
from premoulinette.subject.textutil import collapse_ws

_SKIP_STRINGS = (Comment, Doctype, CData, ProcessingInstruction, Declaration)
_DROP_TAGS = [
    "script", "style", "nav", "noscript", "template", "head", "iframe", "svg", "button",
    "select", "textarea", "input", "meta", "link",
]
_HEADINGS = {f"h{i}": i for i in range(1, 7)}
_CONTAINERS = {
    "div", "section", "article", "main", "header", "footer", "aside", "blockquote", "figure", "figcaption",
    "details", "summary", "center", "body", "html", "form", "dl", "dd", "dt", "fieldset", "li",
}
_BLOCK_TAGS = set(_HEADINGS) | _CONTAINERS | {"p", "pre", "ul", "ol", "table", "hr", "tr", "td", "th"}
_INPUT_TAGS = {"kbd", "b", "strong", "u", "ins"}


def _is_input_tag(tag: Tag) -> bool:
    if tag.name in _INPUT_TAGS:
        return True
    if tag.name == "span":
        return any("input" in c.lower() for c in (tag.get("class") or []))
    return False


def _clean_code(text: str) -> str:
    return text.replace("\xa0", " ").replace("\r", "").replace("\n", " ")


def inline_content(nodes: list[object]) -> tuple[str, list[str]]:
    """Plain text (whitespace collapsed) and inline code contents of a run of inline nodes."""
    pieces: list[str] = []
    codes: list[str] = []

    def rec(node: object) -> None:
        if isinstance(node, NavigableString):
            if not isinstance(node, _SKIP_STRINGS):
                pieces.append(str(node))
            return
        if isinstance(node, str):
            pieces.append(node)
            return
        if not isinstance(node, Tag):
            return
        if node.name == "br":
            pieces.append("\n")
            return
        if node.name in ("code", "tt"):
            text = node.get_text()
            codes.append(_clean_code(text))
            pieces.append(text)
            return
        for child in node.children:
            rec(child)
        if node.name in _BLOCK_TAGS:
            pieces.append(" ")

    for n in nodes:
        rec(n)
    return collapse_ws("".join(pieces)), codes


def pre_content(pre: Tag) -> tuple[str, list[tuple[int, int]], bool]:
    """Verbatim text of a <pre>, user-input spans, and whether a <kbd> was present."""
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    pos = 0
    has_kbd = False

    def rec(node: Tag, in_input: bool) -> None:
        nonlocal pos, has_kbd
        for child in node.children:
            if isinstance(child, NavigableString):
                if isinstance(child, _SKIP_STRINGS):
                    continue
                s = str(child).replace("\xa0", " ")
                if in_input and s:
                    spans.append((pos, pos + len(s)))
                parts.append(s)
                pos += len(s)
            elif isinstance(child, Tag):
                if child.name == "br":
                    parts.append("\n")
                    pos += 1
                    continue
                if child.name == "kbd":
                    has_kbd = True
                rec(child, in_input or _is_input_tag(child))

    rec(pre, False)
    text = "".join(parts)
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s == merged[-1][1]:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    if text.startswith("\n"):  # the newline right after <pre> is not content (HTML spec)
        text = text[1:]
        merged = [(max(0, s - 1), e - 1) for s, e in merged if e - 1 > 0]
    return text, merged, has_kbd


def _has_block_descendant(tag: Tag) -> bool:
    return any(isinstance(d, Tag) and d.name in _BLOCK_TAGS for d in tag.descendants)


class _Walker:
    def __init__(self, builder: DocBuilder) -> None:
        self.b = builder
        self.buf: list[object] = []

    def flush(self) -> None:
        if self.buf:
            text, codes = inline_content(self.buf)
            self.buf = []
            self.b.paragraph(text, codes)

    def walk(self, node: Tag) -> None:
        for child in list(node.children):
            if isinstance(child, NavigableString):
                if not isinstance(child, _SKIP_STRINGS):
                    self.buf.append(child)
                continue
            if not isinstance(child, Tag):
                continue
            self.element(child)

    def element(self, tag: Tag) -> None:
        name = (tag.name or "").lower()
        if name in _HEADINGS:
            self.flush()
            self.b.heading(inline_content([tag])[0], _HEADINGS[name])
        elif name == "pre":
            self.flush()
            self.pre(tag)
        elif name in ("ul", "ol"):
            self.flush()
            self.list(tag)
        elif name == "table":
            self.flush()
            self.table(tag)
        elif name == "hr":
            self.flush()
        elif name == "br":
            self.buf.append("\n")
        elif name == "p" or name in _CONTAINERS:
            self.flush()
            if _has_block_descendant(tag):
                self.walk(tag)
                self.flush()
            else:
                text, codes = inline_content([tag])
                self.b.paragraph(text, codes)
        else:
            self.buf.append(tag)

    def pre(self, tag: Tag) -> None:
        text, spans, has_kbd = pre_content(tag)
        classes = list(tag.get("class") or [])
        inner = tag.find("code")
        if isinstance(inner, Tag):
            classes += list(inner.get("class") or [])
        lang = detect_code_lang(lang_from_classes(classes), text, has_kbd=has_kbd)
        self.b.code(text, lang, spans)

    def list(self, tag: Tag) -> None:
        for li in tag.find_all("li", recursive=False):
            self.list_item(li)

    def list_item(self, li: Tag) -> None:
        nodes: list[object] = []

        def emit() -> None:
            if nodes:
                text, codes = inline_content(nodes)
                nodes.clear()
                self.b.list_item(text, codes)

        for child in li.children:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                emit()
                self.list(child)
            elif isinstance(child, Tag) and child.name == "pre":
                emit()
                self.pre(child)
            elif isinstance(child, Tag) and child.name == "table":
                emit()
                self.table(child)
            else:
                nodes.append(child)
        emit()

    def table(self, tag: Tag) -> None:
        for tr in tag.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            texts: list[str] = []
            codes: list[str] = []
            for cell in cells:
                t, c = inline_content([cell])
                texts.append(t)
                codes += c
            self.b.table_row(" | ".join(texts), codes)


def extract_html(html: str, builder: DocBuilder) -> str | None:
    """Append the blocks of an HTML document (or fragment) to ``builder``; return its <title>."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = collapse_ws(title_tag.get_text()) if isinstance(title_tag, Tag) else None
    for t in soup.find_all(_DROP_TAGS):
        t.decompose()
    for t in soup.find_all("title"):
        t.decompose()
    root = soup.find("body")
    walker = _Walker(builder)
    walker.walk(root if isinstance(root, Tag) else soup)
    walker.flush()
    return title or None
