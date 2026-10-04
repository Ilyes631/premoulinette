"""``def name(params) -> T:`` signature lines -> :class:`FunctionSignature`."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from premoulinette.spec.models import FunctionSignature, Param
from premoulinette.subject.document import Block

_DEF_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)def\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<params>.*)\)\s*(?:->\s*(?P<ret>[^:#]+?))?\s*:?\s*(?:#.*)?$"
)


@dataclass
class FoundSignature:
    signature: FunctionSignature
    block: Block
    line_offset: int
    raw: str
    note: str | None = None


def _from_ast(name: str, params: str, ret: str | None) -> tuple[FunctionSignature, str | None] | None:
    src = f"def {name}({params})" + (f" -> {ret}" if ret else "") + ": pass"
    try:
        fn = ast.parse(src).body[0]
    except SyntaxError:
        return None
    assert isinstance(fn, ast.FunctionDef)
    a = fn.args
    positional = a.posonlyargs + a.args
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
    out: list[Param] = []
    for arg, default in zip(positional, defaults):
        out.append(Param(
            name=arg.arg,
            annotation=ast.unparse(arg.annotation) if arg.annotation else None,
            default=ast.unparse(default) if default is not None else None,
        ))
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        out.append(Param(
            name=arg.arg,
            annotation=ast.unparse(arg.annotation) if arg.annotation else None,
            default=ast.unparse(default) if default is not None else None,
        ))
    note = None
    if a.vararg or a.kwarg:
        note = f"'{name}' takes *args/**kwargs: they are not represented in the parsed signature."
    sig = FunctionSignature(name=name, params=out, return_annotation=ast.unparse(fn.returns) if fn.returns else None)
    return sig, note


def _fallback(name: str, params: str, ret: str | None) -> FunctionSignature:
    out: list[Param] = []
    for part in [p.strip() for p in params.split(",") if p.strip()]:
        default = None
        if "=" in part:
            part, default = (x.strip() for x in part.split("=", 1))
        ann = None
        if ":" in part:
            part, ann = (x.strip() for x in part.split(":", 1))
        if re.fullmatch(r"[A-Za-z_]\w*", part):
            out.append(Param(name=part, annotation=ann or None, default=default))
    return FunctionSignature(name=name, params=out, return_annotation=ret.strip() if ret else None)


def parse_def_line(line: str) -> tuple[FunctionSignature, str | None] | None:
    m = _DEF_LINE_RE.match(line.rstrip())
    if not m:
        return None
    name, params, ret = m.group("name"), m.group("params"), m.group("ret")
    ret = ret.strip() if ret else None
    parsed = _from_ast(name, params, ret)
    if parsed is not None:
        return parsed
    return _fallback(name, params, ret), f"Signature of '{name}' could not be parsed exactly: '{line.strip()}'."


def find_signatures(blocks: list[Block]) -> list[FoundSignature]:
    """Top-level ``def`` lines of non-terminal code blocks, then ``def`` inline code, in document order."""
    found: list[FoundSignature] = []
    seen: set[str] = set()

    def add(sig: FunctionSignature, block: Block, offset: int, raw: str, note: str | None) -> None:
        if sig.name not in seen:
            seen.add(sig.name)
            found.append(FoundSignature(sig, block, offset, raw.strip(), note))

    for block in blocks:
        if block.kind == "code" and block.lang != "terminal":
            lines = block.text.split("\n")
            def_lines = [(i, ln) for i, ln in enumerate(lines) if _DEF_LINE_RE.match(ln.rstrip())]
            if not def_lines:
                continue
            min_indent = min(len(ln) - len(ln.lstrip()) for _, ln in def_lines)
            for i, ln in def_lines:
                if len(ln) - len(ln.lstrip()) != min_indent or ln.lstrip().startswith(">>>"):
                    continue
                parsed = parse_def_line(ln.strip())
                if parsed:
                    add(parsed[0], block, i, ln, parsed[1])
        elif block.kind in ("paragraph", "list_item", "table_row"):
            for code in block.inline_code:
                if code.strip().startswith("def "):
                    parsed = parse_def_line(code.strip())
                    if parsed:
                        add(parsed[0], block, 0, code, parsed[1])
    return found
