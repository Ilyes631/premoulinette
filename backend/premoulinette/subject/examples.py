"""Function call examples: doctests, ``f(x) -> y``, ``f(x) == y``, ``f(x)  # y`` and inline-code prose."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from premoulinette.spec.validate import is_literal
from premoulinette.subject.document import Block
from premoulinette.subject.textutil import PLACEHOLDER_RE, mark

_OPERATORS = ("->", "→", "=>", "⇒", "==")
NO_OUTPUT_NOTE = "No output shown after the call (doctest semantics: the call returns None)."
_EXC_LINE_RE = re.compile(r"^(?P<name>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Iteration))\b")
_RAISES_RE = re.compile(r"(?i)^(?:raises?|l[èe]ve|raise)\s+`?(?P<name>[A-Za-z_]\w*)`?")
_CONNECTOR_RE = re.compile(
    r"(?i)^\s*(?:->|→|=>|⇒|==|=|returns?|should\s+return|must\s+return|gives?|renvoie|retourne|"
    r"doit\s+(?:renvoyer|retourner)|vaut|evaluates\s+to)\s*:?\s*$"
)


@dataclass
class ExampleDraft:
    function: str
    args: list[str]
    kwargs: dict[str, str]
    expected_return: str | None
    expected_exception: str | None
    expected_stdout: str | None
    block: Block
    line_offset: int
    excerpt: str
    note: str | None = None

    def key(self) -> tuple:
        return (self.function, tuple(self.args), tuple(sorted(self.kwargs.items())),
                self.expected_return, self.expected_exception, self.expected_stdout)


@dataclass
class _Call:
    name: str
    args: list[str]
    kwargs: dict[str, str]
    printed: bool


def parse_call(src: str, fn_names: set[str]) -> _Call | None:
    src = src.strip()
    if not src or len(src) > 2000:
        return None
    try:
        node = ast.parse(src, mode="eval").body
    except SyntaxError:
        return None
    printed = False
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
            and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Call)):
        node, printed = node.args[0], True
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)) or node.func.id not in fn_names:
        return None
    args: list[str] = []
    for a in node.args:
        seg = ast.get_source_segment(src, a)
        if isinstance(a, ast.Starred) or seg is None or not is_literal(seg):
            return None
        args.append(seg)
    kwargs: dict[str, str] = {}
    for k in node.keywords:
        seg = ast.get_source_segment(src, k.value)
        if k.arg is None or seg is None or not is_literal(seg):
            return None
        kwargs[k.arg] = seg
    return _Call(node.func.id, args, kwargs, printed)


def parse_expected(text: str) -> tuple[str, str] | None:
    """("return", literal) | ("exception", name) | ("stdout", text) | None."""
    lines = [ln.rstrip() for ln in text.strip("\n").split("\n")]
    stripped = "\n".join(lines).strip()
    if not stripped:
        return None
    if lines[0].strip().startswith("Traceback"):
        m = _EXC_LINE_RE.match(lines[-1].strip())
        return ("exception", m.group("name").rsplit(".", 1)[-1]) if m else None
    m = _RAISES_RE.match(stripped)
    if m:
        return "exception", m.group("name")
    if is_literal(stripped):
        return "return", stripped
    trimmed = stripped.rstrip(".,;")
    if trimmed != stripped and is_literal(trimmed):
        return "return", trimmed
    return "stdout", "\n".join(lines) + "\n"


def _top_level_operators(s: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(s):
        ch = s[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0:
            for op in _OPERATORS:
                if s.startswith(op, i):
                    found.append((i, op))
                    i += len(op) - 1
                    break
        i += 1
    return found


def _split_comment(s: str) -> tuple[str, str] | None:
    quote: str | None = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return s[:i], s[i + 1:]
    return None


def parse_example_line(line: str, fn_names: set[str]) -> tuple[_Call, tuple[str, str]] | None:
    s = re.sub(r"^\s*(?:[-*•]\s+)?", "", line).strip()
    if not s or s.startswith(("def ", ">>>", "#")):
        return None
    split = _split_comment(s)
    if split:
        call = parse_call(split[0], fn_names)
        if call:
            value = re.sub(r"(?i)^\s*(?:->|→|=>|==|returns?|renvoie|retourne|:)\s*", "", split[1].strip())
            exp = parse_expected(value)
            if exp and exp[0] in ("return", "exception"):
                return call, exp
        return None
    for pos, op in _top_level_operators(s):
        call = parse_call(s[:pos], fn_names)
        if call:
            exp = parse_expected(s[pos + len(op):].strip())
            if exp and exp[0] in ("return", "exception"):
                return call, exp
            return None
    return None


def _draft(call: _Call, exp: tuple[str, str], block: Block, offset: int, text: str) -> ExampleDraft:
    kind, value = exp
    note = None
    expected_return = value if kind == "return" else None
    if call.printed:
        note = "Example printed the result: the expected value is what print() shows."
    if kind == "stdout":
        note = "Expected output is not a Python literal: interpreted as text printed by the call."
    return ExampleDraft(
        function=call.name, args=call.args, kwargs=call.kwargs,
        expected_return=expected_return,
        expected_exception=value if kind == "exception" else None,
        expected_stdout=value if kind == "stdout" else None,
        block=block, line_offset=offset, excerpt=text.strip(), note=note,
    )


def _doctests(block: Block, fn_names: set[str]) -> list[ExampleDraft]:
    lines = block.text.split("\n")
    out: list[ExampleDraft] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s.startswith(">>>"):
            line_ex = parse_example_line(lines[i], fn_names)
            if line_ex:
                out.append(_draft(*line_ex, block, i, lines[i]))
            i += 1
            continue
        start = i
        call_src = s[3:].strip()
        i += 1
        while i < len(lines) and lines[i].strip().startswith("..."):
            call_src += "\n" + lines[i].strip()[3:].strip()
            i += 1
        output: list[str] = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(">>>"):
            output.append(lines[i])
            i += 1
        call = parse_call(call_src, fn_names)
        if call is None:
            continue
        exp = parse_expected("\n".join(output))
        excerpt_text = "\n".join(lines[start:i])
        if exp is None:
            draft = _draft(call, ("return", "None"), block, start, excerpt_text)
            draft.note = NO_OUTPUT_NOTE
            out.append(draft)
        else:
            out.append(_draft(call, exp, block, start, excerpt_text))
    return out


def _prose_examples(block: Block, fn_names: set[str]) -> list[ExampleDraft]:
    out: list[ExampleDraft] = []
    for code in block.inline_code:
        ex = parse_example_line(code, fn_names)
        if ex:
            out.append(_draft(*ex, block, 0, code))
    marked = mark(block.text, block.inline_code)
    placeholders = list(PLACEHOLDER_RE.finditer(marked.text))
    for a, b in zip(placeholders, placeholders[1:]):
        between = marked.text[a.end():b.start()]
        if not _CONNECTOR_RE.match(between):
            continue
        call = parse_call(marked.codes[int(a.group(1))], fn_names)
        if call is None:
            continue
        exp = parse_expected(marked.codes[int(b.group(1))])
        if exp and exp[0] in ("return", "exception"):
            out.append(_draft(call, exp, block, 0, marked.unmark(marked.text[a.start():b.end()])))
    for offset, line in enumerate(block.text.split("\n")):
        ex = parse_example_line(line, fn_names)
        if ex:
            out.append(_draft(*ex, block, offset, line))
    return out


def extract_examples(blocks: list[Block], fn_names: set[str]) -> list[ExampleDraft]:
    """All examples calling one of ``fn_names``, in document order, deduplicated."""
    if not fn_names:
        return []
    found: list[ExampleDraft] = []
    for block in blocks:
        if block.kind == "code":
            if block.lang != "terminal":
                found += _doctests(block, fn_names)
        elif block.kind in ("paragraph", "list_item", "table_row"):
            found += _prose_examples(block, fn_names)
    unique: list[ExampleDraft] = []
    seen: set[tuple] = set()
    for ex in found:
        if ex.key() not in seen:
            seen.add(ex.key())
            unique.append(ex)
    return unique
