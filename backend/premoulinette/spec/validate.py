"""Static validation of a :class:`PracticalSpec` (what the spec editor shows as errors/warnings).

Also exposes the restricted-expression helpers used by the subject parsers: rule conditions,
rule results and references must belong to the safe subset understood by
``premoulinette.testgen.oracle`` (never evaluated with ``eval``).
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel

from premoulinette.spec.models import FunctionSpec, PracticalSpec

SAFE_FUNCS = frozenset({"abs", "min", "max", "round", "len", "int", "float", "str", "bool", "sum", "sorted"})
CONSTANT_NAMES = frozenset({"True", "False", "None"})
MAX_EXPR_LEN = 2000

_ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.Tuple, ast.List, ast.Dict, ast.Set, ast.Subscript, ast.Slice, ast.JoinedStr,
    ast.FormattedValue, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.Invert, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class SpecIssue(BaseModel):
    level: Literal["error", "warning"]
    path: str
    message: str


# ----------------------------------------------------------------------------------------------
# Restricted expressions / literals
# ----------------------------------------------------------------------------------------------


def _fallback_parse(src: str) -> ast.expr:
    try:
        tree = ast.parse(src.strip(), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"not a valid expression: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"construct not allowed in a rule expression: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCS or node.keywords:
                raise ValueError("only calls to " + ", ".join(sorted(SAFE_FUNCS)) + " are allowed")
            if any(isinstance(a, ast.Starred) for a in node.args):
                raise ValueError("starred arguments are not allowed")
    return tree.body


def parse_restricted_expr(src: str) -> ast.expr:
    """Parse ``src`` as a restricted expression; raise ``ValueError`` if it is not in the safe subset.

    Uses ``premoulinette.testgen.oracle.parse_expr`` when available (single source of truth), falling
    back to a local whitelist check otherwise.
    """
    if not isinstance(src, str) or not src.strip():
        raise ValueError("empty expression")
    if len(src) > MAX_EXPR_LEN:
        raise ValueError("expression too long")
    try:
        from premoulinette.testgen.oracle import OracleError, parse_expr
    except Exception:  # module not available (yet) or broken: local check
        return _fallback_parse(src)
    try:
        return parse_expr(src.strip())
    except OracleError as exc:
        raise ValueError(str(exc)) from exc
    except Exception:
        return _fallback_parse(src)


def expression_names(node: ast.AST) -> set[str]:
    """Variable names used by an expression (constants and safe-function call targets excluded)."""
    call_funcs = {id(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}
    return {
        n.id for n in ast.walk(node)
        if isinstance(n, ast.Name) and n.id not in CONSTANT_NAMES and id(n) not in call_funcs
    }


def restricted_names(src: str) -> set[str] | None:
    """Names used by ``src`` if it is a valid restricted expression, else None."""
    try:
        return expression_names(parse_restricted_expr(src))
    except ValueError:
        return None


def is_literal(src: str | None) -> bool:
    if src is None or len(src) > 100_000:
        return False
    try:
        ast.literal_eval(src.strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return False
    return True


def is_safe_relpath(path: str) -> str | None:
    """Return a problem description if ``path`` is not a clean POSIX relative path, else None."""
    if not path or not path.strip():
        return "empty path"
    if "\\" in path:
        return "path must use '/' separators"
    if path.startswith("/") or _WINDOWS_DRIVE_RE.match(path):
        return "path must be relative to the repository root"
    parts = path.rstrip("/").split("/")
    if any(p in ("..", "") for p in parts):
        return "path must not contain '..' or empty components"
    if any(p == "." for p in parts):
        return "path must not contain '.' components"
    return None


# ----------------------------------------------------------------------------------------------
# validate_spec
# ----------------------------------------------------------------------------------------------


def _check_rules(fn: FunctionSpec, base: str, issues: list[SpecIssue]) -> None:
    params = {p.name for p in fn.signature.params}

    def check_expr(src: str, path: str, what: str) -> None:
        try:
            names = expression_names(parse_restricted_expr(src))
        except ValueError as exc:
            issues.append(SpecIssue(level="error", path=path, message=f"Invalid {what} '{src}': {exc}"))
            return
        unknown = sorted(names - params)
        if unknown:
            issues.append(SpecIssue(
                level="error", path=path,
                message=f"{what.capitalize()} '{src}' uses unknown name(s) {unknown}; parameters are {sorted(params)}",
            ))

    for r_i, rule in enumerate(fn.rules):
        rpath = f"{base}.rules[{r_i}]"
        if rule.when is not None:
            check_expr(rule.when, f"{rpath}.when", "condition")
        if rule.returns is not None:
            check_expr(rule.returns, f"{rpath}.returns", "rule result")
        if rule.returns is None and rule.raises is None:
            issues.append(SpecIssue(level="warning", path=rpath, message="Rule has neither 'returns' nor 'raises'."))
        if rule.raises is not None and not re.fullmatch(r"[A-Za-z_]\w*", rule.raises):
            issues.append(SpecIssue(level="error", path=f"{rpath}.raises", message=f"Invalid exception name '{rule.raises}'."))
    if fn.reference is not None:
        check_expr(fn.reference, f"{base}.reference", "reference")


def _check_function(fn: FunctionSpec, base: str, ex_functions: set[str], issues: list[SpecIssue]) -> None:
    sig = fn.signature
    if not re.fullmatch(r"[A-Za-z_]\w*", sig.name):
        issues.append(SpecIssue(level="error", path=f"{base}.signature.name", message=f"Invalid function name '{sig.name}'."))
    seen_params: set[str] = set()
    for p_i, p in enumerate(sig.params):
        if p.name in seen_params:
            issues.append(SpecIssue(level="error", path=f"{base}.signature.params[{p_i}]", message=f"Duplicate parameter '{p.name}'."))
        seen_params.add(p.name)
        if p.default is not None and not is_literal(p.default):
            issues.append(SpecIssue(level="error", path=f"{base}.signature.params[{p_i}].default",
                                    message=f"Default '{p.default}' is not a Python literal."))
    _check_rules(fn, base, issues)
    for t_i, test in enumerate(fn.tests):
        tpath = f"{base}.tests[{t_i}]"
        if test.function not in ex_functions:
            issues.append(SpecIssue(level="error", path=f"{tpath}.function",
                                    message=f"Test '{test.id}' calls '{test.function}', which is not defined in this exercise."))
        elif test.function != fn.name:
            issues.append(SpecIssue(level="warning", path=f"{tpath}.function",
                                    message=f"Test '{test.id}' calls '{test.function}' but is listed under '{fn.name}'."))
        for a_i, arg in enumerate(test.args):
            if not is_literal(arg):
                issues.append(SpecIssue(level="error", path=f"{tpath}.args[{a_i}]", message=f"Argument '{arg}' is not a Python literal."))
        for key, val in test.kwargs.items():
            if not re.fullmatch(r"[A-Za-z_]\w*", key):
                issues.append(SpecIssue(level="error", path=f"{tpath}.kwargs", message=f"Invalid keyword name '{key}'."))
            if not is_literal(val):
                issues.append(SpecIssue(level="error", path=f"{tpath}.kwargs.{key}", message=f"Keyword value '{val}' is not a Python literal."))
        if test.expected_return is not None and not is_literal(test.expected_return):
            issues.append(SpecIssue(level="error", path=f"{tpath}.expected_return",
                                    message=f"Expected value '{test.expected_return}' is not a Python literal."))


def validate_spec(spec: PracticalSpec) -> list[SpecIssue]:
    """Return every problem found in ``spec`` (errors block analysis quality, warnings inform)."""
    issues: list[SpecIssue] = []

    for f_i, req in enumerate(spec.structure.files):
        problem = is_safe_relpath(req.path)
        if problem:
            issues.append(SpecIssue(level="error", path=f"structure.files[{f_i}].path", message=f"'{req.path}': {problem}."))

    ex_ids = Counter(e.id for e in spec.exercises)
    for dup in sorted(i for i, n in ex_ids.items() if n > 1):
        issues.append(SpecIssue(level="error", path="exercises", message=f"Duplicate exercise id '{dup}'."))

    test_ids = Counter([t.id for _, _, t in spec.all_function_tests()] + [t.id for _, t in spec.all_script_tests()])
    for dup in sorted(i for i, n in test_ids.items() if n > 1):
        issues.append(SpecIssue(level="error", path="exercises", message=f"Duplicate test id '{dup}'."))

    for e_i, ex in enumerate(spec.exercises):
        base = f"exercises[{e_i}]"
        problem = is_safe_relpath(ex.file_path)
        if problem:
            issues.append(SpecIssue(level="error", path=f"{base}.file_path", message=f"'{ex.file_path}': {problem}."))
        fn_names = [f.name for f in ex.functions]
        for dup in sorted({n for n in fn_names if fn_names.count(n) > 1}):
            issues.append(SpecIssue(level="error", path=f"{base}.functions", message=f"Function '{dup}' is defined twice."))
        for fn_i, fn in enumerate(ex.functions):
            _check_function(fn, f"{base}.functions[{fn_i}]", set(fn_names), issues)

        if ex.kind == "script" and ex.script is None:
            issues.append(SpecIssue(level="error", path=f"{base}.script", message="Script exercise without a script specification."))
        if ex.kind == "functions" and not ex.functions:
            issues.append(SpecIssue(level="warning", path=f"{base}.functions", message="Functions exercise without any function."))
        if ex.script is not None:
            for p_i, prompt in enumerate(ex.script.prompts):
                if prompt == "":
                    issues.append(SpecIssue(level="warning", path=f"{base}.script.prompts[{p_i}]", message="Empty prompt."))

        n_fn_tests = sum(len(f.tests) for f in ex.functions)
        n_script_tests = len(ex.script.tests) if ex.script else 0
        if ex.kind == "functions" and ex.functions and n_fn_tests == 0:
            has_oracle = any(f.rules or f.reference for f in ex.functions)
            msg = "No explicit test: only derived tests from rules can be generated." if has_oracle else \
                "No test and no rule: only presence/signature checks are possible."
            issues.append(SpecIssue(level="warning", path=base, message=f"Exercise '{ex.id}': {msg}"))
        if ex.kind == "script" and ex.script is not None and n_script_tests == 0:
            issues.append(SpecIssue(level="warning", path=f"{base}.script.tests",
                                    message=f"Exercise '{ex.id}': no example session, its output cannot be checked."))
    return issues
