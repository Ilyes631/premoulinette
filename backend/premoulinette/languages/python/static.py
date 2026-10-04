"""Static analysis of student Python files.

Student code is NEVER executed here: sources are decoded, parsed with :func:`ast.parse` and the tree is
handed to :func:`compile` only to surface the errors Python reports *before* running a file
(``'return' outside function``, ``'break' outside loop``...). ``compile`` builds a code object that is
immediately discarded; nothing is imported, evaluated or run.

Name resolution rule (documented contract): a call ``name(...)`` is a *builtin* call iff ``name`` is a
Python builtin and is not bound anywhere in the enclosing scopes (module defs/classes/imports/assignments,
for/with/except targets, parameters, comprehension targets, ``global`` declarations...). So a student's
own ``def max(...)`` is a *local* call, never a forbidden builtin.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
import warnings
import weakref
from pathlib import Path, PurePosixPath

from premoulinette.languages.python.builtins_catalog import PURE_BUILTINS, PYTHON_BUILTINS
from premoulinette.languages.python.static_models import (
    CallSite,
    ConstructUse,
    FunctionInfo,
    ImportInfo,
    ModuleInfo,
    ParamInfo,
    ReturnInfo,
    StringLiteral,
    SyntaxErrorInfo,
    TopLevelEffect,
)

__all__ = ["analyze_source", "analyze_file", "analyze_project", "source_lines_of", "split_source_lines"]

_LINE_SPLIT = re.compile(r"\r\n|\r|\n")   # same line numbering as the ast module
_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMP_NODES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SCOPE_NODES = _FUNC_NODES + (ast.Lambda, ast.ClassDef) + _COMP_NODES
_MAX_SRC = 120
_PSEUDO_FILENAME = "<student-code>"

# ------------------------------------------------------------------------------------------------
# Source registry: lets the checks build code excerpts without re-reading files.
# Keyed by id(ModuleInfo); the entry is dropped when the ModuleInfo is garbage collected.
# ------------------------------------------------------------------------------------------------
_SOURCES: dict[int, list[str]] = {}


def split_source_lines(source: str) -> list[str]:
    """Source lines without terminators, numbered like the ast module (line n = index n-1)."""
    lines = _LINE_SPLIT.split(source)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _remember(info: ModuleInfo, lines: list[str]) -> ModuleInfo:
    key = id(info)
    _SOURCES[key] = lines
    weakref.finalize(info, _SOURCES.pop, key, None)
    return info


def source_lines_of(info: ModuleInfo) -> list[str] | None:
    """Source lines of a ModuleInfo produced by this module (None if unknown, e.g. a copy)."""
    return _SOURCES.get(id(info))


# ------------------------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------------------------


def analyze_source(source: str, rel_path: str) -> ModuleInfo:
    """Analyze one module from its source text (ast only; never executes it)."""
    if source.startswith("﻿"):
        source = source[1:]
    lines = split_source_lines(source)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # A pseudo file name: CPython must never read a same-named file from the server's cwd to
            # fill SyntaxError.text (the text is taken from ``lines`` instead).
            tree = ast.parse(source, filename=_PSEUDO_FILENAME)
            compile(tree, _PSEUDO_FILENAME, "exec", dont_inherit=True)   # compiler-level errors only; never run
    except SyntaxError as exc:
        return _remember(ModuleInfo(path=rel_path, ok=False, syntax_error=_syntax_info(exc, lines),
                                    line_count=len(lines)), lines)
    except ValueError as exc:   # e.g. null bytes on older interpreters
        info = SyntaxErrorInfo(message=str(exc) or "invalid source code", line=None, kind="SyntaxError")
        return _remember(ModuleInfo(path=rel_path, ok=False, syntax_error=info, line_count=len(lines)), lines)
    except (RecursionError, MemoryError):
        info = SyntaxErrorInfo(message="the code is too deeply nested to be compiled", kind="SyntaxError")
        return _remember(ModuleInfo(path=rel_path, ok=False, syntax_error=info, line_count=len(lines)), lines)
    try:
        info = _Analyzer(rel_path, lines).run(tree)
    except RecursionError:
        err = SyntaxErrorInfo(message="the code is too deeply nested to be analyzed", kind="SyntaxError")
        info = ModuleInfo(path=rel_path, ok=False, syntax_error=err, line_count=len(lines))
    return _remember(info, lines)


def analyze_file(path: Path, rel_path: str) -> ModuleInfo:
    """Analyze one file. Decoding follows Python (BOM / PEP 263 cookie, default UTF-8);
    undecodable files give ``ok=False`` with ``encoding_error``."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return ModuleInfo(path=rel_path, ok=False, encoding_error=f"The file could not be read: {exc.strerror or exc}.")
    source, error = decode_source(data)
    if source is None:
        lines = split_source_lines(data.decode("utf-8", errors="replace"))
        return _remember(ModuleInfo(path=rel_path, ok=False, encoding_error=error, line_count=len(lines)), lines)
    return analyze_source(source, rel_path)


def analyze_project(root: Path, files: list[str]) -> dict[str, ModuleInfo]:
    """Analyze every ``.py`` file of ``files`` (POSIX paths relative to ``root``)."""
    base = Path(root).resolve()
    out: dict[str, ModuleInfo] = {}
    for rel in files:
        rel_posix = rel.replace("\\", "/")
        if not rel_posix.endswith(".py") or rel_posix in out:
            continue
        pure = PurePosixPath(rel_posix)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            continue
        path = base.joinpath(*pure.parts)
        try:
            if not path.resolve().is_relative_to(base) or not path.is_file():
                continue
        except OSError:
            continue
        out[rel_posix] = analyze_file(path, rel_posix)
    return out


def decode_source(data: bytes) -> tuple[str | None, str | None]:
    """(source, None) or (None, human readable encoding error). Same rules as the interpreter."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    except SyntaxError as exc:
        return None, f"Invalid encoding declaration: {exc.msg if hasattr(exc, 'msg') else exc}."
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:
        line = data[: exc.start].count(b"\n") + 1
        bad = data[exc.start: exc.start + 1]
        byte = f"0x{bad[0]:02x}" if bad else "?"
        enc = "UTF-8" if encoding.lower().replace("_", "-") in ("utf-8", "utf-8-sig") else encoding
        return None, (f"The file is not valid {enc}: byte {byte} on line {line} cannot be decoded. "
                      f"Save the file with the UTF-8 encoding.")
    except LookupError:
        return None, f"Unknown encoding declared in the file: {encoding}."
    if text.startswith("﻿"):
        text = text[1:]
    return text, None


# ------------------------------------------------------------------------------------------------
# Syntax errors
# ------------------------------------------------------------------------------------------------


def _syntax_info(exc: SyntaxError, lines: list[str]) -> SyntaxErrorInfo:
    line = exc.lineno if isinstance(exc.lineno, int) and exc.lineno > 0 else None
    text = exc.text
    if line is not None and line <= len(lines):
        text = lines[line - 1]
    if text is not None:
        text = text.rstrip("\r\n")
    col = exc.offset if isinstance(exc.offset, int) and exc.offset > 0 else None
    end_col = getattr(exc, "end_offset", None)
    end_col = end_col if isinstance(end_col, int) and end_col > 0 else None
    return SyntaxErrorInfo(message=exc.msg or str(exc), line=line, col=col, end_col=end_col, text=text,
                           kind=type(exc).__name__)


# ------------------------------------------------------------------------------------------------
# Scopes
# ------------------------------------------------------------------------------------------------


class _Scope:
    __slots__ = ("kind", "parent", "bound", "imports", "global_decl")

    def __init__(self, kind: str, parent: _Scope | None) -> None:
        self.kind = kind                    # module | function | lambda | class | comprehension
        self.parent = parent
        self.bound: set[str] = set()
        self.imports: dict[str, str] = {}   # bound name -> dotted module path
        self.global_decl: set[str] = set()


def _bind_target_names(node: ast.AST, scope: _Scope) -> None:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            scope.bound.add(sub.id)


def _bind_params(args: ast.arguments, scope: _Scope) -> None:
    for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        scope.bound.add(a.arg)
    if args.vararg:
        scope.bound.add(args.vararg.arg)
    if args.kwarg:
        scope.bound.add(args.kwarg.arg)


def _scan_bindings(roots: list[ast.AST], scope: _Scope) -> None:
    """Record every name bound by ``roots`` in ``scope`` (nested scopes are not entered)."""
    stack: list[ast.AST] = list(reversed(roots))
    while stack:
        node = stack.pop()
        if isinstance(node, (*_FUNC_NODES, ast.ClassDef)):
            scope.bound.add(node.name)
            continue
        if isinstance(node, (ast.Lambda, *_COMP_NODES)):
            continue
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                scope.bound.add(node.id)
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    scope.bound.add(alias.asname)
                    scope.imports[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    scope.bound.add(head)
                    scope.imports[head] = head
            continue
        if isinstance(node, ast.ImportFrom):
            base = "." * (node.level or 0) + (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                scope.bound.add(bound)
                scope.imports[bound] = (base + "." + alias.name) if base and not base.endswith(".") else base + alias.name
            continue
        if isinstance(node, ast.ExceptHandler) and node.name:
            scope.bound.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            scope.bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            scope.bound.add(node.rest)
        elif isinstance(node, ast.Global):
            scope.global_decl.update(node.names)
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _new_scope(node: ast.AST, parent: _Scope | None) -> _Scope:
    if isinstance(node, ast.Module):
        scope = _Scope("module", None)
        _scan_bindings(list(node.body), scope)
        return scope
    if isinstance(node, _FUNC_NODES):
        scope = _Scope("function", parent)
        _bind_params(node.args, scope)
        _scan_bindings(list(node.body), scope)
    elif isinstance(node, ast.Lambda):
        scope = _Scope("lambda", parent)
        _bind_params(node.args, scope)
        _scan_bindings([node.body], scope)
    elif isinstance(node, ast.ClassDef):
        scope = _Scope("class", parent)
        _scan_bindings(list(node.body), scope)
    else:  # comprehension
        scope = _Scope("comprehension", parent)
        for gen in node.generators:   # type: ignore[attr-defined]
            _bind_target_names(gen.target, scope)
    scope.bound -= scope.global_decl
    return scope


# ------------------------------------------------------------------------------------------------
# Analyzer
# ------------------------------------------------------------------------------------------------

_CONSTRUCT_OF: dict[type, str] = {
    ast.For: "for", ast.AsyncFor: "for", ast.While: "while",
    ast.ListComp: "comprehension", ast.SetComp: "comprehension", ast.DictComp: "comprehension",
    ast.GeneratorExp: "comprehension", ast.Lambda: "lambda", ast.Try: "try", ast.Global: "global",
    ast.ClassDef: "class", ast.Import: "import", ast.ImportFrom: "import", ast.With: "with",
    ast.AsyncWith: "with", ast.Yield: "yield", ast.YieldFrom: "yield", ast.NamedExpr: "walrus",
    ast.Match: "match",
}
if hasattr(ast, "TryStar"):
    _CONSTRUCT_OF[ast.TryStar] = "try"

_EFFECT_RANK = {"loop": 1, "call": 2, "print": 3, "input": 4}


def _short(text: str, limit: int = _MAX_SRC) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 - unparse of exotic nodes must never break the analysis
        return None


def _is_main_guard(test: ast.expr) -> bool:
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    left, right = test.left, test.comparators[0]

    def is_name(n: ast.expr) -> bool:
        return isinstance(n, ast.Name) and n.id == "__name__"

    def is_main(n: ast.expr) -> bool:
        return isinstance(n, ast.Constant) and n.value == "__main__"

    return (is_name(left) and is_main(right)) or (is_main(left) and is_name(right))


def _docstring_ids(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, *_FUNC_NODES)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _return_info(node: ast.Return) -> ReturnInfo:
    value = node.value
    if value is None:
        return ReturnInfo(line=node.lineno, value_src=None, value_kind="none")
    src = _unparse(value)
    if isinstance(value, ast.Constant):
        return ReturnInfo(line=node.lineno, value_src=src, value_kind="constant",
                          constant_type=type(value.value).__name__)
    if (isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd))
            and isinstance(value.operand, ast.Constant)
            and type(value.operand.value) in (int, float, complex)):
        return ReturnInfo(line=node.lineno, value_src=src, value_kind="constant",
                          constant_type=type(value.operand.value).__name__)
    if isinstance(value, ast.Name):
        return ReturnInfo(line=node.lineno, value_src=src, value_kind="name")
    if isinstance(value, ast.Call):
        return ReturnInfo(line=node.lineno, value_src=src, value_kind="call")
    return ReturnInfo(line=node.lineno, value_src=src, value_kind="expression")


def _params(args: ast.arguments) -> list[ParamInfo]:
    out: list[ParamInfo] = []
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for i, a in enumerate(positional):
        kind = "posonly" if i < len(args.posonlyargs) else "positional"
        out.append(ParamInfo(name=a.arg, annotation=_unparse(a.annotation), default=_unparse(defaults[i]), kind=kind))
    if args.vararg:
        out.append(ParamInfo(name=args.vararg.arg, annotation=_unparse(args.vararg.annotation), kind="vararg"))
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        out.append(ParamInfo(name=a.arg, annotation=_unparse(a.annotation), default=_unparse(d), kind="kwonly"))
    if args.kwarg:
        out.append(ParamInfo(name=args.kwarg.arg, annotation=_unparse(args.kwarg.annotation), kind="varkw"))
    return out


class _Analyzer(ast.NodeVisitor):
    def __init__(self, rel_path: str, lines: list[str]) -> None:
        self.path = rel_path
        self.lines = lines
        self.scope: _Scope | None = None
        self.module_scope: _Scope | None = None
        self.top_fn: str | None = None
        self.fn_stack: list[tuple[FunctionInfo, _Scope | None]] = []   # (info, scope binding its name)
        self.import_time = True
        self.direct_io: dict[int, str] = {}
        self.docstrings: set[int] = set()
        self.functions: list[FunctionInfo] = []
        self.nested: list[FunctionInfo] = []
        self.classes: list[str] = []
        self.imports: list[ImportInfo] = []
        self.calls: list[CallSite] = []
        self.constructs: list[ConstructUse] = []
        self.strings: list[StringLiteral] = []
        self.effects: dict[int, TopLevelEffect] = {}
        self.has_main_guard = False

    # ---- driver -----------------------------------------------------------------------------
    def run(self, tree: ast.Module) -> ModuleInfo:
        self.docstrings = _docstring_ids(tree)
        self.module_scope = self.scope = _new_scope(tree, None)
        for node in ast.walk(tree):   # `global x` in a function binds x at module level
            if isinstance(node, ast.Global):
                self.module_scope.bound.update(node.names)
        for stmt in tree.body:
            self.visit(stmt)
        return ModuleInfo(
            path=self.path, ok=True, line_count=len(self.lines), functions=self.functions,
            nested_functions=self.nested, classes=self.classes, imports=self.imports, calls=self.calls,
            constructs=self.constructs, strings=self.strings,
            top_level_effects=[self.effects[k] for k in sorted(self.effects)],
            has_main_guard=self.has_main_guard, defined_names=sorted(self.module_scope.bound),
        )

    # ---- helpers ----------------------------------------------------------------------------
    def lookup(self, name: str) -> _Scope | None:
        scope, first = self.scope, True
        while scope is not None:
            if scope.kind == "class" and not first:
                scope = scope.parent
                continue
            if name in scope.global_decl:
                return self.module_scope if name in self.module_scope.bound else None  # type: ignore[union-attr]
            if name in scope.bound:
                return scope
            first = False
            scope = scope.parent
        return None

    def is_builtin(self, name: str) -> bool:
        return name in PYTHON_BUILTINS and self.lookup(name) is None

    def construct(self, name: str, line: int) -> None:
        self.constructs.append(ConstructUse(name=name, line=line, in_function=self.top_fn))

    def effect(self, kind: str, line: int) -> None:
        src = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        current = self.effects.get(line)
        if current is None or _EFFECT_RANK[kind] > _EFFECT_RANK[current.kind]:
            self.effects[line] = TopLevelEffect(kind=kind, line=line, src=_short(src))  # type: ignore[arg-type]

    def in_scope(self, node: ast.AST, body: list[ast.AST], *, function: bool = False) -> None:
        saved_scope, saved_time = self.scope, self.import_time
        self.scope = _new_scope(node, self.scope)
        if function:
            self.import_time = False
        for child in body:
            self.visit(child)
        self.scope, self.import_time = saved_scope, saved_time

    def generic_visit(self, node: ast.AST) -> None:
        kind = _CONSTRUCT_OF.get(type(node))
        if kind is not None and hasattr(node, "lineno"):
            self.construct(kind, node.lineno)  # type: ignore[attr-defined]
        super().generic_visit(node)

    # ---- definitions ------------------------------------------------------------------------
    def visit_decorators(self, decorators: list[ast.expr]) -> None:
        saved = self.import_time
        self.import_time = False   # decorator factories run at import but are not student "effects"
        for expr in decorators:
            self.visit(expr)
        self.import_time = saved

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # The annotation is not code the student "uses" (``x: int = 0`` does not call int).
        self.visit(node.target)
        if node.value is not None:
            self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.visit_decorators(list(node.decorator_list))
        for expr in [*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]]:
            self.visit(expr)
        info = FunctionInfo(
            name=node.name, line=node.lineno, end_line=node.end_lineno or node.lineno, params=_params(node.args),
            return_annotation=_unparse(node.returns), decorators=[_unparse(d) or "" for d in node.decorator_list],
            docstring=ast.get_docstring(node), nested=self.scope is not self.module_scope,
        )
        if info.nested:
            self.nested.append(info)
        else:
            existing = next((i for i, f in enumerate(self.functions) if f.name == node.name), None)
            if existing is None:
                self.functions.append(info)
            else:   # redefinition: the last `def` wins, as in Python
                self.functions[existing] = info
        saved_top = self.top_fn
        if self.top_fn is None:
            self.top_fn = node.name
        self.fn_stack.append((info, self.scope))
        self.in_scope(node, list(node.body), function=True)
        self.fn_stack.pop()
        self.top_fn = saved_top

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.construct("lambda", node.lineno)
        for expr in [*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]]:
            self.visit(expr)
        self.in_scope(node, [node.body], function=True)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.construct("class", node.lineno)
        self.classes.append(node.name)
        self.visit_decorators(list(node.decorator_list))
        for expr in [*node.bases, *node.keywords]:
            self.visit(expr)
        self.in_scope(node, list(node.body))

    def _visit_comprehension(self, node: ast.AST) -> None:
        self.construct("comprehension", node.lineno)  # type: ignore[attr-defined]
        generators: list[ast.comprehension] = node.generators  # type: ignore[attr-defined]
        self.visit(generators[0].iter)   # evaluated in the enclosing scope
        saved = self.scope
        self.scope = _new_scope(node, self.scope)
        for i, gen in enumerate(generators):
            if i:
                self.visit(gen.iter)
            for cond in gen.ifs:
                self.visit(cond)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)  # type: ignore[attr-defined]
        self.scope = saved

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _visit_comprehension

    # ---- statements -------------------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        self.construct("import", node.lineno)
        for alias in node.names:
            self.imports.append(ImportInfo(module=alias.name, names=[], line=node.lineno, in_function=self.top_fn))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.construct("import", node.lineno)
        module = "." * (node.level or 0) + (node.module or "")
        self.imports.append(ImportInfo(module=module, names=[a.name for a in node.names], line=node.lineno,
                                       in_function=self.top_fn))

    def visit_Return(self, node: ast.Return) -> None:
        if self.fn_stack:
            fn = self.fn_stack[-1][0]
            ret = _return_info(node)
            fn.returns.append(ret)
            if node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None):
                fn.has_value_return = True
        if node.value is not None:
            self.visit(node.value)

    def visit_If(self, node: ast.If) -> None:
        if self.import_time and self.scope is self.module_scope and _is_main_guard(node.test):
            self.has_main_guard = True
            self.visit(node.test)
            saved = self.import_time
            self.import_time = False
            for stmt in node.body:
                self.visit(stmt)
            self.import_time = saved
            for stmt in node.orelse:
                self.visit(stmt)
            return
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        if self.import_time and isinstance(node.test, ast.Constant) and node.test.value:
            self.effect("loop", node.lineno)
        self.generic_visit(node)

    # ---- expressions ------------------------------------------------------------------------
    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        if self.is_builtin(node.id):
            self.calls.append(CallSite(name=node.id, kind="builtin", line=node.lineno, col=node.col_offset,
                                       end_col=node.end_col_offset, in_function=self.top_fn, referenced_only=True))
        elif node.id == "__builtins__" and self.lookup(node.id) is None:
            self.calls.append(CallSite(name="__builtins__", kind="unknown", line=node.lineno, col=node.col_offset,
                                       end_col=node.end_col_offset, in_function=self.top_fn, referenced_only=True))

    def _module_path(self, node: ast.expr) -> str | None:
        """Dotted path when ``node`` is ``mod.a.b`` with ``mod`` bound by an import, else None."""
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        scope = self.lookup(node.id)
        if scope is None or node.id not in scope.imports:
            return None
        return ".".join([scope.imports[node.id], *reversed(parts)])

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        line, col, end_col = node.lineno, node.col_offset, node.end_col_offset
        if isinstance(func, ast.Name):
            name = func.id
            if self.is_builtin(name):
                kind = "builtin"
            elif self.lookup(name) is not None:
                kind = "local"
            else:
                kind = "unknown"
            self.calls.append(CallSite(name=name, kind=kind, line=line, col=col, end_col=end_col, in_function=self.top_fn))  # type: ignore[arg-type]
            if kind == "builtin" and name in ("print", "input") and self.fn_stack:
                fn = self.fn_stack[-1][0]
                (fn.prints if name == "print" else fn.inputs).append(line)
            if kind == "builtin" and name in ("print", "input"):
                for arg in node.args:
                    self.direct_io[id(arg)] = name
            self._check_recursion(name, line)
            if self.import_time:
                if kind == "builtin":
                    if name in ("print", "input"):
                        self.effect(name, line)
                    elif name not in PURE_BUILTINS:
                        self.effect("call", line)
                else:
                    self.effect("call", line)
        elif isinstance(func, ast.Attribute):
            dotted = self._module_path(func)
            if dotted is not None:
                self.calls.append(CallSite(name=dotted, kind="module_attr", line=line, col=col, end_col=end_col,
                                           in_function=self.top_fn))
                if self.import_time:
                    self.effect("call", line)
            else:
                self.calls.append(CallSite(name=func.attr, kind="method", line=line, col=col, end_col=end_col,
                                           in_function=self.top_fn))
            self.visit(func.value)
        else:
            self.calls.append(CallSite(name=_short(_unparse(func) or "<call>", 60), kind="unknown", line=line, col=col,
                                       end_col=end_col, in_function=self.top_fn))
            if self.import_time:
                self.effect("call", line)
            self.visit(func)
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)

    def _check_recursion(self, name: str, line: int) -> None:
        target = self.lookup(name)
        for info, binding_scope in reversed(self.fn_stack):
            if info.name == name:
                if target is binding_scope and target is not None:
                    info.is_recursive = True
                    self.construct("recursion", line)
                return

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, str) or id(node) in self.docstrings:
            return
        self.strings.append(StringLiteral(
            value=node.value, line=node.lineno, end_line=node.end_lineno or node.lineno, col=node.col_offset,
            end_col=node.end_col_offset or node.col_offset, is_fstring=False, in_call=self.direct_io.get(id(node)),
            in_function=self.top_fn,
        ))

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self.construct("fstring", node.lineno)
        parts: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            else:
                parts.append("{}")
        self.strings.append(StringLiteral(
            value="".join(parts), line=node.lineno, end_line=node.end_lineno or node.lineno, col=node.col_offset,
            end_col=node.end_col_offset or node.col_offset, is_fstring=True, in_call=self.direct_io.get(id(node)),
            in_function=self.top_fn,
        ))
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                self._visit_formatted(part)

    def _visit_formatted(self, node: ast.FormattedValue) -> None:
        self.visit(node.value)
        spec = node.format_spec
        if isinstance(spec, ast.JoinedStr):   # nested fields of the format spec: f"{x:{width}}"
            for part in spec.values:
                if isinstance(part, ast.FormattedValue):
                    self._visit_formatted(part)
