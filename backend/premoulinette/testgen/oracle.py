"""Restricted expression evaluator ("oracle") for behaviour rules and reference expressions.

Rules of the spec (``speed <= limit``, ``f"{s // 3600:02}"``...) are parsed with ``ast.parse`` and
interpreted node by node over a small whitelist. Nothing is ever passed to ``eval``/``exec`` or
compiled to bytecode. Resource guards keep hostile expressions (``9 ** 9 ** 9``, ``"a" * 10**9``,
``f"{x:999999999}"``) from exhausting memory or CPU.
"""
from __future__ import annotations

import ast
import math
import operator
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from premoulinette.spec.models import BehaviorRule, FunctionSpec, Param

MAX_SOURCE_CHARS = 10_000
MAX_LITERAL_CHARS = 1_000_000
MAX_DEPTH = 50
MAX_POW_EXPONENT = 1000
MAX_ITEMS = 10_000
MAX_INT_BITS = 100_000
MAX_FORMAT_WIDTH = 10_000
MAX_NESTED_WEIGHT = 1_000_000


class OracleError(Exception):
    """The expression is outside the safe subset, or its evaluation failed (division by zero...)."""


SAFE_FUNCS: dict[str, Callable[..., Any]] = {
    "abs": abs, "min": min, "max": max, "round": round, "len": len, "int": int,
    "float": float, "str": str, "bool": bool, "sum": sum, "sorted": sorted,
}
_SAFE_KWARGS: dict[str, frozenset[str]] = {
    "round": frozenset({"ndigits"}),
    "sorted": frozenset({"reverse"}),
    "sum": frozenset({"start"}),
    "min": frozenset({"default"}),
    "max": frozenset({"default"}),
}

_BINOPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.LShift: operator.lshift, ast.RShift: operator.rshift, ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_, ast.BitXor: operator.xor,
}
_UNARYOPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_, ast.Invert: operator.invert,
}
_CMPOPS: dict[type[ast.cmpop], Callable[[Any, Any], Any]] = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Is: operator.is_, ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.Tuple, ast.List, ast.Dict, ast.Set, ast.Subscript, ast.Slice, ast.JoinedStr, ast.FormattedValue,
    ast.Call, ast.keyword, ast.And, ast.Or, *_BINOPS, *_UNARYOPS, *_CMPOPS,
)
_CONSTANT_TYPES = (int, float, complex, str, bytes, bool, type(None))
_CONVERSIONS: dict[int, Callable[[Any], str]] = {-1: lambda v: v, 115: str, 114: repr, 97: ascii}
_PRINTF_FIELD = re.compile(r"%[#0\- +]*(\*|\d*)(?:\.(\*|\d*))?")
_SIZED = (str, bytes, list, tuple, dict, set, frozenset)


# ------------------------------------------------------------------------------------------------
# Parsing + validation
# ------------------------------------------------------------------------------------------------


def parse_expr(src: str) -> ast.expr:
    """Parse ``src`` as a single expression of the safe subset (raises :class:`OracleError`)."""
    if not isinstance(src, str):
        raise OracleError("expression must be a string")
    text = src.strip()
    if not text:
        raise OracleError("empty expression")
    if len(text) > MAX_SOURCE_CHARS:
        raise OracleError("expression is too long")
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        raise OracleError(f"not a valid expression: {exc}") from None
    _validate(tree.body)
    return tree.body


def _validate(root: ast.expr) -> None:
    stack: list[tuple[ast.AST, int]] = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise OracleError("expression is too deeply nested")
        _check_node(node)
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


def _check_node(node: ast.AST) -> None:
    if not isinstance(node, _ALLOWED_NODES):
        raise OracleError(f"'{type(node).__name__}' is not allowed in rules")
    if isinstance(node, ast.Name) and node.id.startswith("__"):
        raise OracleError(f"name '{node.id}' is not allowed")
    elif isinstance(node, ast.Constant) and not isinstance(node.value, _CONSTANT_TYPES):
        raise OracleError(f"constant {node.value!r} is not allowed")
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCS:
            raise OracleError(f"call to '{ast.unparse(node.func)}' is not allowed")
        allowed = _SAFE_KWARGS.get(node.func.id, frozenset())
        for kw in node.keywords:
            if kw.arg is None or kw.arg not in allowed:
                raise OracleError(f"keyword argument '{kw.arg}' is not allowed for {node.func.id}()")
    elif isinstance(node, ast.FormattedValue) and node.conversion not in _CONVERSIONS:
        raise OracleError("unsupported f-string conversion")
    elif isinstance(node, ast.Dict) and any(k is None for k in node.keys):
        raise OracleError("dict unpacking is not allowed")


# ------------------------------------------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------------------------------------------


def safe_eval(src: str, env: Mapping[str, object]) -> object:
    """Evaluate a safe-subset expression over ``env`` (parameter name -> value)."""
    return _Evaluator(env).run(parse_expr(src))


def literal(src: str) -> object:
    """``ast.literal_eval`` that only raises :class:`OracleError`."""
    if not isinstance(src, str):
        raise OracleError("literal must be a string")
    if len(src) > MAX_LITERAL_CHARS:
        raise OracleError("literal is too long")
    try:
        return ast.literal_eval(src.strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError) as exc:
        raise OracleError(f"not a Python literal: {src.strip()[:60]!r} ({type(exc).__name__})") from None


class _Evaluator:
    def __init__(self, env: Mapping[str, object]) -> None:
        self._env = env

    def run(self, node: ast.expr) -> object:
        try:
            return self._eval(node)
        except OracleError:
            raise
        except ZeroDivisionError:
            raise OracleError("division by zero") from None
        except (ArithmeticError, TypeError, ValueError, LookupError, AttributeError,
                RecursionError, MemoryError) as exc:
            raise OracleError(f"{type(exc).__name__}: {exc}") from None

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in self._env:
                raise OracleError(f"unknown name '{node.id}'")
            return self._env[node.id]
        if isinstance(node, ast.BoolOp):
            return self._bool_op(node)
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.IfExp):
            return self._eval(node.body) if self._eval(node.test) else self._eval(node.orelse)
        return _check_size(self._eval_computed(node))

    def _eval_computed(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BinOp):
            left, right = self._eval(node.left), self._eval(node.right)
            _guard_binop(node.op, left, right)
            return _BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp):
            return _UNARYOPS[type(node.op)](self._eval(node.operand))
        if isinstance(node, ast.Tuple):
            return tuple(self._eval(e) for e in node.elts)
        if isinstance(node, ast.List):
            return [self._eval(e) for e in node.elts]
        if isinstance(node, ast.Set):
            return {self._eval(e) for e in node.elts}
        if isinstance(node, ast.Dict):
            return {self._eval(k): self._eval(v) for k, v in zip(node.keys, node.values) if k is not None}
        if isinstance(node, ast.Subscript):
            return self._eval(node.value)[self._eval(node.slice)]
        if isinstance(node, ast.Slice):
            parts = (node.lower, node.upper, node.step)
            return slice(*(None if p is None else self._eval(p) for p in parts))
        if isinstance(node, ast.JoinedStr):
            return "".join(str(self._eval(v)) for v in node.values)
        if isinstance(node, ast.FormattedValue):
            return self._formatted(node)
        if isinstance(node, ast.Call):
            return self._call(node)
        raise OracleError(f"'{type(node).__name__}' is not allowed in rules")

    def _bool_op(self, node: ast.BoolOp) -> Any:
        value: Any = None
        for operand in node.values:
            value = self._eval(operand)
            if isinstance(node.op, ast.And) and not value:
                return value
            if isinstance(node.op, ast.Or) and value:
                return value
        return value

    def _compare(self, node: ast.Compare) -> bool:
        left = self._eval(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self._eval(comparator)
            if not _CMPOPS[type(op)](left, right):
                return False
            left = right
        return True

    def _formatted(self, node: ast.FormattedValue) -> str:
        value = _CONVERSIONS[node.conversion](self._eval(node.value))
        spec = "" if node.format_spec is None else str(self._eval(node.format_spec))
        _guard_widths(spec)
        return format(value, spec)

    def _call(self, node: ast.Call) -> Any:
        assert isinstance(node.func, ast.Name)  # guaranteed by _check_node
        name = node.func.id
        args = [self._eval(a) for a in node.args]
        kwargs = {kw.arg: self._eval(kw.value) for kw in node.keywords if kw.arg is not None}
        _guard_call(name, args, kwargs)
        return SAFE_FUNCS[name](*args, **kwargs)


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _nested_weight(value: Any, limit: int) -> int:
    """Elements + characters reachable from ``value`` (stops counting past ``limit``)."""
    weight = 0
    stack = [value]
    while stack and weight <= limit:
        item = stack.pop()
        if isinstance(item, (str, bytes)):
            weight += len(item)
        elif isinstance(item, dict):
            weight += len(item)
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set, frozenset)):
            weight += len(item)
            stack.extend(item)
    return weight


def _check_size(value: Any) -> Any:
    if isinstance(value, _SIZED) and len(value) > MAX_ITEMS:
        raise OracleError(f"result is too large (> {MAX_ITEMS} items)")
    if _is_int(value) and value.bit_length() > MAX_INT_BITS:
        raise OracleError("integer result is too large")
    if isinstance(value, (list, tuple, set, frozenset, dict)) and _nested_weight(value, MAX_NESTED_WEIGHT) > MAX_NESTED_WEIGHT:
        raise OracleError("nested result is too large")
    return value


def _guard_call(name: str, args: list[Any], kwargs: dict[str, Any]) -> None:
    if name == "round":
        ndigits = args[1] if len(args) > 1 else kwargs.get("ndigits")
        if _is_int(ndigits) and abs(ndigits) > MAX_POW_EXPONENT:
            raise OracleError("round() precision is too large")
    elif name == "sum":
        start = args[1] if len(args) > 1 else kwargs.get("start", 0)
        items = args[0] if args else ()
        if isinstance(start, _SIZED) or (isinstance(items, _SIZED) and any(isinstance(x, _SIZED) for x in items)):
            raise OracleError("sum() only adds numbers in rules")


def _guard_binop(op: ast.operator, left: Any, right: Any) -> None:
    """Refuse operations whose result would be huge *before* computing them."""
    if isinstance(op, ast.Pow):
        if isinstance(right, (int, float)) and right > MAX_POW_EXPONENT:
            raise OracleError(f"exponent {right} is too large (max {MAX_POW_EXPONENT})")
        if _is_int(left) and _is_int(right) and right > 0 and abs(left).bit_length() * right > MAX_INT_BITS:
            raise OracleError("power result is too large")
    elif isinstance(op, ast.Mult):
        for seq, count in ((left, right), (right, left)):
            if isinstance(seq, _SIZED) and isinstance(count, int) and len(seq) * count > MAX_ITEMS:
                raise OracleError("repeated sequence is too large")
        if _is_int(left) and _is_int(right) and left.bit_length() + right.bit_length() > MAX_INT_BITS:
            raise OracleError("product is too large")
    elif isinstance(op, ast.LShift):
        if _is_int(left) and _is_int(right) and left.bit_length() + right > MAX_INT_BITS:
            raise OracleError("shift result is too large")
    elif isinstance(op, ast.Add):
        if isinstance(left, _SIZED) and isinstance(right, _SIZED) and len(left) + len(right) > MAX_ITEMS:
            raise OracleError("concatenation is too large")
    elif isinstance(op, ast.Mod) and isinstance(left, str):
        for width, precision in _PRINTF_FIELD.findall(left):
            _guard_widths(f"{width}.{precision}")


def _guard_widths(spec: str) -> None:
    if "*" in spec:
        raise OracleError("'*' widths are not supported")
    for number in re.findall(r"\d+", spec):
        if len(number) > 6 or int(number) > MAX_FORMAT_WIDTH:
            raise OracleError(f"format width/precision {number} is too large")


# ------------------------------------------------------------------------------------------------
# Expected outcome of a call according to the rules / reference of a function
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OracleOutcome:
    """What the subject says ``fn(*args)`` should do."""

    kind: Literal["value", "raises", "unknown", "error"]
    value: object | None = None
    exception: str | None = None
    rule: BehaviorRule | None = None      # matching rule (None when the reference was used)
    rule_text: str | None = None
    reason: str | None = None             # why the outcome is unknown / an error


def rule_text(rule: BehaviorRule) -> str:
    condition = rule.when if rule.when else "otherwise"
    if rule.raises:
        result = f"raises {rule.raises}"
    else:
        result = rule.returns if rule.returns is not None else "?"
    return f"{condition} → {result}"


def bind_args(fn: FunctionSpec, args: list[object], kwargs: Mapping[str, object] | None = None) -> dict[str, object]:
    """Map a call onto the parameter names of ``fn`` (defaults applied). Raises OracleError."""
    params = fn.signature.params
    if len(args) > len(params):
        raise OracleError(f"{fn.name}() takes {len(params)} argument(s), {len(args)} given")
    env: dict[str, object] = {p.name: v for p, v in zip(params, args)}
    names = {p.name for p in params}
    for key, value in (kwargs or {}).items():
        if key not in names:
            raise OracleError(f"{fn.name}() has no parameter '{key}'")
        if key in env:
            raise OracleError(f"{fn.name}() got multiple values for '{key}'")
        env[key] = value
    for p in params:
        if p.name not in env:
            if p.default is None:
                raise OracleError(f"{fn.name}() is missing argument '{p.name}'")
            env[p.name] = literal(p.default)
    return {p.name: env[p.name] for p in params}


def expected_outcome(fn: FunctionSpec, args: list[object], kwargs: Mapping[str, object] | None = None) -> OracleOutcome:
    """First matching rule (``when=None`` = otherwise), then the reference expression."""
    try:
        env = bind_args(fn, args, kwargs)
        for rule in fn.rules:
            if rule.when is not None and not safe_eval(rule.when, env):
                continue
            text = rule_text(rule)
            if rule.raises:
                return OracleOutcome("raises", exception=rule.raises, rule=rule, rule_text=text)
            if rule.returns is None:
                return OracleOutcome("unknown", rule=rule, rule_text=text, reason="the matching rule has no value")
            return OracleOutcome("value", value=safe_eval(rule.returns, env), rule=rule, rule_text=text)
        if fn.reference:
            return OracleOutcome("value", value=safe_eval(fn.reference, env), rule_text=f"returns {fn.reference}")
    except OracleError as exc:
        return OracleOutcome("error", reason=str(exc))
    reason = "no rule matches these arguments" if fn.rules else "no rule or reference expression"
    return OracleOutcome("unknown", reason=reason)


def expected_for(fn: FunctionSpec, args: list[object]) -> tuple[bool, object | None, str | None]:
    """``(known, value, rule_text)`` for ``fn(*args)`` according to its rules, then its reference."""
    outcome = expected_outcome(fn, args)
    if outcome.kind == "value":
        return True, outcome.value, outcome.rule_text
    return False, None, outcome.rule_text


# ------------------------------------------------------------------------------------------------
# Parameter typing helpers (shared with the test generator)
# ------------------------------------------------------------------------------------------------

_SIMPLE_TYPES = {"int": int, "float": float, "str": str, "bool": bool}
_TYPE_DEFAULTS: dict[str, object] = {"int": 1, "float": 1.0, "str": "a", "bool": True}
_NO_VALUE = object()


def simple_annotation(annotation: str | None) -> str | None:
    """'int' / 'float' / 'str' / 'bool' when the annotation is exactly one of them, else None."""
    if annotation is None:
        return None
    text = annotation.strip().strip("'\"").strip()
    if text.startswith("builtins."):
        text = text[len("builtins."):]
    return text if text in _SIMPLE_TYPES else None


def param_kind(param: Param, base_value: object = _NO_VALUE) -> str | None:
    """Simple type of a parameter: from its annotation, else from a sample value."""
    simple = simple_annotation(param.annotation)
    if simple is not None:
        return simple
    if param.annotation is not None:
        return "other"
    for name, typ in (("bool", bool), ("int", int), ("float", float), ("str", str)):
        if type(base_value) is typ:
            return name
    return None


def value_key(value: object) -> tuple[str, object]:
    """Hashable identity of an argument value: 1 and 1.0 are the same call, True and 1 are not."""
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("num", value)
    if isinstance(value, str):
        return ("str", value)
    return ("repr", repr(value))


def assignment_key(fn: FunctionSpec, assignment: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple(value_key(assignment.get(p.name)) for p in fn.signature.params)


def bind_literal_args(fn: FunctionSpec, args: list[str], kwargs: Mapping[str, str] | None = None) -> dict[str, object]:
    """Bound parameter values of a call given as literal sources (raises OracleError)."""
    return bind_args(fn, [literal(a) for a in args], {k: literal(v) for k, v in (kwargs or {}).items()})


def base_values(fn: FunctionSpec) -> dict[str, object]:
    """Reference argument values: the first explicit test's arguments, else type defaults."""
    base: dict[str, object] = {}
    ordered = sorted(fn.tests, key=lambda t: t.origin.provenance not in ("explicit", "user"))
    for test in ordered:
        try:
            base = bind_literal_args(fn, test.args, test.kwargs)
            break
        except OracleError:
            continue
    for p in fn.signature.params:
        if p.name in base:
            continue
        if p.default is not None:
            try:
                base[p.name] = literal(p.default)
                continue
            except OracleError:
                pass
        kind = simple_annotation(p.annotation) or ("int" if p.annotation is None else None)
        if kind is not None:
            base[p.name] = _TYPE_DEFAULTS[kind]
    return base


# ------------------------------------------------------------------------------------------------
# Boundary values
# ------------------------------------------------------------------------------------------------

_BOUNDARY_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


@dataclass(frozen=True)
class BoundaryCase:
    assignment: dict[str, object]          # every parameter, in signature order
    rule: BehaviorRule
    comparison: str                        # "speed <= limit"
    description: str                       # "speed == limit"


@dataclass
class _BoundaryContext:
    names: set[str]
    kinds: dict[str, str | None]
    base: dict[str, object]
    points: list[tuple[dict[str, object], str, str]] = field(default_factory=list)


def boundary_cases(fn: FunctionSpec, rules: list[BehaviorRule] | None = None) -> list[BoundaryCase]:
    """Assignments around every comparison of the rules' conditions (deduplicated, in rule order)."""
    params = fn.signature.params
    base = base_values(fn)
    ctx = _BoundaryContext(
        names={p.name for p in params},
        kinds={p.name: param_kind(p, base.get(p.name, _NO_VALUE)) for p in params},
        base=base,
    )
    seen: set[tuple[tuple[str, object], ...]] = set()
    cases: list[BoundaryCase] = []
    for rule in fn.rules if rules is None else rules:
        if not rule.when:
            continue
        try:
            tree = parse_expr(rule.when)
        except OracleError:
            continue
        for left, op, right in _comparisons(tree):
            for update, description in _points(left, op, right, ctx):
                assignment = {**base, **update}
                if any(p.name not in assignment for p in params):
                    continue
                ordered = {p.name: assignment[p.name] for p in params}
                key = assignment_key(fn, ordered)
                if key in seen:
                    continue
                seen.add(key)
                comparison = ast.unparse(ast.Compare(left=left, ops=[op], comparators=[right]))
                cases.append(BoundaryCase(ordered, rule, comparison, description))
    return cases


def boundary_values(fn: FunctionSpec) -> list[dict[str, object]]:
    """Parameter assignments around the comparisons found in ``fn.rules``."""
    return [case.assignment for case in boundary_cases(fn)]


def _comparisons(tree: ast.expr) -> Iterator[tuple[ast.expr, ast.cmpop, ast.expr]]:
    """Every pairwise comparison, chains split: ``2 < x <= 5`` -> (2 < x), (x <= 5)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for i, op in enumerate(node.ops):
                yield operands[i], op, operands[i + 1]


def _param_name(node: ast.expr, names: set[str]) -> str | None:
    return node.id if isinstance(node, ast.Name) and node.id in names else None


def _constant(node: ast.expr) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return _NO_VALUE


def _points(left: ast.expr, op: ast.cmpop, right: ast.expr, ctx: _BoundaryContext) -> list[tuple[dict[str, object], str]]:
    if not isinstance(op, _BOUNDARY_OPS):
        return []
    lp, rp = _param_name(left, ctx.names), _param_name(right, ctx.names)
    if lp and rp:
        return _param_vs_param(lp, rp, ctx) if lp != rp else []
    if lp:
        param, const = lp, _constant(right)
    elif rp:
        param, const = rp, _constant(left)
    else:
        return []
    if const is _NO_VALUE:
        return []
    return [({param: v}, f"{param} == {v!r}") for v in _values_around(const, ctx.kinds.get(param), op)]


def _values_around(const: object, kind: str | None, op: ast.cmpop) -> list[object]:
    if isinstance(const, bool):
        return []
    if isinstance(const, str):
        return [const] if kind in (None, "str") and isinstance(op, (ast.Eq, ast.NotEq)) else []
    if not isinstance(const, (int, float)) or kind not in (None, "int", "float"):
        return []
    if not math.isfinite(const):
        return []
    if kind == "float" or (kind is None and isinstance(const, float)):
        c = float(const)
        return [c, c + 0.5, c - 0.5]
    if isinstance(const, float):
        low, high = math.floor(const), math.ceil(const)
        if low != high:
            return [low, high]
        const = low
    return [const - 1, const, const + 1]


def _param_vs_param(left: str, right: str, ctx: _BoundaryContext) -> list[tuple[dict[str, object], str]]:
    """Vary ``left`` around the base value of ``right``: equal, +step, -step."""
    pivot = ctx.base.get(right, _NO_VALUE)
    kind = ctx.kinds.get(left)
    if not isinstance(pivot, (int, float)) or isinstance(pivot, bool) or kind not in (None, "int", "float"):
        return []
    if kind == "float":
        pivot = float(pivot)
    elif kind == "int" and isinstance(pivot, float):
        if not pivot.is_integer():
            return []
        pivot = int(pivot)
    step: int | float = 0.5 if isinstance(pivot, float) else 1
    return [
        ({left: pivot}, f"{left} == {right}"),
        ({left: pivot + step}, f"{left} == {right} + {step}"),
        ({left: pivot - step}, f"{left} == {right} - {step}"),
    ]
