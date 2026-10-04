"""Deterministic minimal fixes attached to failing checks (``CheckResult.fix``).

Every builder returns ``None`` when it is not sure. Fixes are suggestions only: nothing here ever writes
to disk. Patches are minimal unified diffs (``--- a/x`` / ``+++ b/x``, one line of context) built from the
original source lines, so indentation and the rest of the line are preserved.

Command fixes (git mv / git add) use ``patch=None, before=None, after="<command>"``.
"""
from __future__ import annotations

import ast
import logging
import re
import textwrap
from dataclasses import dataclass
from typing import Callable

from premoulinette.explain._evidence import (
    changed_lines,
    constraint_name,
    expected_and_found_paths,
    found_function_name,
    id_suffix,
    lines_with_op,
    literal_str,
    stdout_diff,
    subject_path,
    text_pair,
)
from premoulinette.explain._literals import find_text_edit, scan_line
from premoulinette.explain._patch import new_file_patch, replace_lines_patch, split_lines
from premoulinette.explain._shell import GITIGNORE_LINES, gitignore_pattern, sh_path
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo
from premoulinette.results.models import CheckResult, Fix

logger = logging.getLogger(__name__)

Sources = dict[str, str]
Modules = dict[str, ModuleInfo]
Builder = Callable[[CheckResult, Sources, Modules], "Fix | None"]

_BUILDERS: dict[str, Builder] = {}
_FIXABLE_STATUSES = ("fail", "warning", "bonus")
_RETURN_WORD = re.compile(r"\breturn\b")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")

BUILTIN_HINTS: dict[str, str] = {
    "abs": "use a condition: if the value is negative, take its opposite (-x)",
    "max": "compare the values two by two and keep the largest in a variable",
    "min": "compare the values two by two and keep the smallest in a variable",
    "sum": "accumulate the elements in a variable with a loop",
    "round": "use integer arithmetic (int(), //, %)",
    "sorted": "sort with loops and comparisons",
    "eval": "convert explicitly with int() or float()",
    "len": "count the elements with a loop",
}


def _builder(*diagnoses: str) -> Callable[[Builder], Builder]:
    def register(fn: Builder) -> Builder:
        for diagnosis in diagnoses:
            _BUILDERS[diagnosis] = fn
        return fn

    return register


def build_fix(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    """The minimal deterministic fix for ``check``, or None when no safe suggestion exists."""
    builder = _BUILDERS.get(check.diagnosis or "")
    if builder is None:
        return None
    try:
        return builder(check, sources, modules)
    except Exception:  # a fix is a convenience: never let it break an analysis
        logger.exception("fix builder failed for %s", check.id)
        return None


def attach_fixes(checks: list[CheckResult], sources: Sources, modules: Modules) -> None:
    """Set ``check.fix`` on failing/warning/bonus checks that have no fix yet and a deterministic one exists."""
    for check in checks:
        if check.fix is not None or check.status not in _FIXABLE_STATUSES:
            continue
        fix = build_fix(check, sources, modules)
        if fix is not None:
            check.fix = fix


# ---------------------------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------------------------


@dataclass
class _Source:
    path: str
    lines: list[str]
    ends_with_newline: bool
    module: ModuleInfo | None

    def line(self, number: int) -> str | None:
        return self.lines[number - 1] if 1 <= number <= len(self.lines) else None

    def patch(self, changes: dict[int, str]) -> str:
        return replace_lines_patch(self.path, self.lines, self.ends_with_newline, changes)


def _resolve(check: CheckResult, sources: Sources, modules: Modules, hint: str | None = None) -> _Source | None:
    ev = check.evidence
    candidates = [hint, check.location.file if check.location else None, check.file, ev.code.file if ev and ev.code else None]
    key = next((c for c in candidates if c and c in sources), None)
    if key is None:
        for cand in (c for c in candidates if c):
            matches = [k for k in sources if k.endswith("/" + cand)]
            if len(matches) == 1:
                key = matches[0]
                break
    if key is None:
        return None
    lines, ends_with_newline = split_lines(sources[key])
    return _Source(key, lines, ends_with_newline, modules.get(key))


def _function(module: ModuleInfo | None, name: str | None) -> FunctionInfo | None:
    if module is None or not name:
        return None
    return module.function(name) or next((f for f in module.nested_functions if f.name == name), None)


def _literal_value(src: str | None) -> object:
    if src is None:
        return None
    try:
        return ast.literal_eval(src)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def _single(changes: dict[int, str], src: _Source) -> tuple[str | None, str | None]:
    if len(changes) != 1:
        return None, None
    number, new = next(iter(changes.items()))
    return (src.line(number) or "").strip(), new.strip()


def _replace_string_constant(line: str, value: str, new_source: str) -> str | None:
    """Replace the unique plain string literal equal to ``value`` after ``return`` on ``line``."""
    literals = scan_line(line)
    if not literals:
        return None
    matches = [lit for lit in literals if lit.decoded == value]
    if len(matches) != 1:
        return None
    lit = matches[0]
    if not _RETURN_WORD.search(line[: lit.start]):
        return None
    return line[: lit.start] + new_source + line[lit.end:]


# ---------------------------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------------------------


@_builder("str_instead_of_bool")
def _fix_str_instead_of_bool(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    src = _resolve(check, sources, modules)
    fn = _function(src.module if src else None, check.function)
    if src is None or fn is None:
        return None
    changes: dict[int, str] = {}
    for ret in fn.returns:
        value = _literal_value(ret.value_src)
        if not isinstance(value, str) or value not in ("True", "False"):
            continue
        new = _replace_string_constant(src.line(ret.line) or "", str(value), str(value))
        if new is None:
            return None  # a half-fixed function would still be wrong: propose nothing
        changes[ret.line] = new
    if not changes:
        return None
    before, after = _single(changes, src)
    return Fix(
        summary='Return the booleans True/False instead of the strings "True"/"False".',
        file=src.path, patch=src.patch(changes), before=before, after=after, confidence="high",
    )


@_builder("number_as_str")
def _fix_number_as_str(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    ev = check.evidence
    src = _resolve(check, sources, modules)
    fn = _function(src.module if src else None, check.function)
    if src is None or fn is None or ev is None or ev.expected_value is None:
        return None
    expected_type = ev.expected_value.type
    actual = literal_str(ev.actual_value)
    changes: dict[int, str] = {}
    fixed_values: set[str] = set()
    for ret in fn.returns:
        value = _literal_value(ret.value_src)
        if not isinstance(value, str) or not _NUMBER.fullmatch(value):
            continue
        if type(_literal_value(value)).__name__ != expected_type:
            return None
        new = _replace_string_constant(src.line(ret.line) or "", value, value)
        if new is None:
            return None
        changes[ret.line] = new
        fixed_values.add(value)
    if not changes or (actual is not None and actual not in fixed_values):
        return None  # the returned string does not come from a constant we can rewrite
    before, after = _single(changes, src)
    return Fix(summary="Return the number itself, not a string containing it.", file=src.path,
               patch=src.patch(changes), before=before, after=after, confidence="high")


# ---------------------------------------------------------------------------------------------
# Texts (returned strings, prompts, printed lines)
# ---------------------------------------------------------------------------------------------


def _text_fix(check: CheckResult, src: _Source, line_no: int | None, expected: str, actual: str,
              string_lines: list[int], what: str) -> Fix | None:
    """Edit the literal on the located line; else the unique literal among ``string_lines``."""
    if line_no is not None:
        edit = find_text_edit(src.line(line_no) or "", actual, expected)
        confidence = "high"
    else:
        edit = None
    if edit is None:
        found = []
        for number in sorted(set(string_lines)):
            candidate = find_text_edit(src.line(number) or "", actual, expected)
            if candidate is not None:
                found.append((number, candidate))
        if len(found) != 1:
            return None
        line_no, edit = found[0]
        confidence = "medium"
    old = src.line(line_no) or ""
    changes = {line_no: edit.apply(old)}
    return Fix(
        summary=f"Change the {what} on line {line_no} so it matches the subject exactly.",
        file=src.path, patch=src.patch(changes), before=old.strip(), after=changes[line_no].strip(),
        confidence=confidence,
    )


def _string_lines(src: _Source, *, function: str | None = None, in_call: str | None = None) -> list[int]:
    if src.module is None:
        return []
    return [
        s.line for s in src.module.strings
        if s.line == s.end_line
        and (function is None or s.in_function == function)
        and (in_call is None or s.in_call == in_call)
    ]


@_builder("wrong_string")
def _fix_wrong_string(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    pair = text_pair(check)
    src = _resolve(check, sources, modules)
    if pair is None or src is None:
        return None
    line_no = check.location.line if check.location else None
    return _text_fix(check, src, line_no, pair[0], pair[1], _string_lines(src, function=check.function), "returned string")


@_builder("prompt_mismatch")
def _fix_prompt(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    pair = text_pair(check)
    src = _resolve(check, sources, modules)
    if pair is None or src is None:
        return None
    line_no = check.location.line if check.location else None
    return _text_fix(check, src, line_no, pair[0], pair[1], _string_lines(src, in_call="input"), "input() prompt")


@_builder("stdout_mismatch")
def _fix_stdout(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    diff = stdout_diff(check)
    changed = changed_lines(diff)
    if not changed or lines_with_op(diff, "missing") or lines_with_op(diff, "extra"):
        return None
    first = changed[0]
    origin = first.source
    if origin is None or origin.line is None:
        return None
    if any(line.source is None or (line.source.file, line.source.line) != (origin.file, origin.line) for line in changed):
        return None  # several source lines are involved: not a single minimal fix
    if first.expected is None or first.actual is None or first.expected_eol != first.actual_eol:
        return None
    if any((line.expected, line.actual) != (first.expected, first.actual) for line in changed):
        return None
    src = _resolve(check, sources, modules, hint=origin.file)
    if src is None:
        return None
    return _text_fix(check, src, origin.line, first.expected, first.actual, [], "printed text")


# ---------------------------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------------------------


@_builder("wrong_function_name")
def _fix_function_name(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    src = _resolve(check, sources, modules)
    if src is None or src.module is None or not check.function:
        return None
    found = found_function_name(check, [f.name for f in src.module.functions])
    fn = _function(src.module, found)
    if found is None or fn is None or found == check.function:
        return None
    old = src.line(fn.line) or ""
    match = re.match(rf"^(\s*(?:async\s+)?def\s+){re.escape(found)}(?=\s*\()", old)
    if match is None:
        return None
    new = match.group(1) + check.function + old[match.end():]
    calls = sorted({c.line for c in src.module.calls if c.name == found and c.kind in ("local", "unknown")})
    summary = f"Rename the function {found} to {check.function}: the grader calls it by its exact name."
    if calls:
        summary += f" Also rename the call(s) to {found} on line(s) {', '.join(map(str, calls))}."
    return Fix(summary=summary, file=src.path, patch=src.patch({fn.line: new}), before=old.strip(), after=new.strip(),
               confidence="high")


def _print_call_in_loop(function_source: str, print_line: int) -> bool | None:
    """True if the print on ``print_line`` (1-based in ``function_source``) is inside a loop; None if unparsable."""
    try:
        tree = ast.parse(textwrap.dedent(function_source))
    except SyntaxError:
        return None

    def visit(node: ast.AST, in_loop: bool) -> bool | None:
        for child in ast.iter_child_nodes(node):
            loop = in_loop or isinstance(node, (ast.For, ast.AsyncFor, ast.While))
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "print" \
                    and child.lineno == print_line:
                return loop
            found = visit(child, loop)
            if found is not None:
                return found
        return None

    return visit(tree, False)


@_builder("prints_instead_of_returns")
def _fix_print_to_return(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    src = _resolve(check, sources, modules)
    fn = _function(src.module if src else None, check.function)
    if src is None or fn is None or fn.has_value_return or len(fn.prints) != 1:
        return None
    line_no = fn.prints[0]
    old = src.line(line_no) or ""
    stripped = old.lstrip()
    indent = old[: len(old) - len(stripped)]
    try:
        tree = ast.parse(stripped)
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return None
    call = tree.body[0].value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print"
            and len(call.args) == 1 and not call.keywords and not isinstance(call.args[0], ast.Starred)
            and call.end_lineno == 1 and call.end_col_offset is not None):
        return None
    arg = call.args[0]
    expected_type = check.evidence.expected_value.type if check.evidence and check.evidence.expected_value else None
    is_text = isinstance(arg, ast.JoinedStr) or (isinstance(arg, ast.Constant) and isinstance(arg.value, str))
    if is_text and expected_type not in (None, "str"):
        return None
    function_source = "\n".join(src.lines[fn.line - 1: fn.end_line])
    if _print_call_in_loop(function_source, line_no - fn.line + 1) is not False:
        return None
    arg_src = ast.get_source_segment(stripped, arg)
    if arg_src is None:
        return None
    rest = stripped.encode("utf-8")[call.end_col_offset:].decode("utf-8")
    new = f"{indent}return {arg_src}{rest}"
    return Fix(
        summary=f"Return the value instead of printing it in {check.function}.",
        file=src.path, patch=src.patch({line_no: new}), before=old.strip(), after=new.strip(), confidence="medium",
    )


# ---------------------------------------------------------------------------------------------
# Repository: files and git
# ---------------------------------------------------------------------------------------------


@_builder("missing_gitignore")
def _fix_gitignore(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    path = check.file if check.file and check.file.endswith(".gitignore") else ".gitignore"
    if path in sources:
        return None
    return Fix(
        summary=f"Create {path} at the repository root, then git add {path} and commit.",
        file=path, patch=new_file_patch(path, list(GITIGNORE_LINES)), confidence="high",
    )


@_builder("parasite_file")
def _fix_parasite(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    path = id_suffix(check, "structure:parasite:") or check.file
    if not path:
        return None
    return Fix(
        summary=(f"Stop tracking it without deleting your local copy: git rm -r --cached {sh_path(path)}, "
                 f"then add {gitignore_pattern(path)} to .gitignore and commit."),
        file=path, confidence="high",
    )


@_builder("misplaced_file", "wrong_case_path")
def _fix_move(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    expected, found = expected_and_found_paths(check)
    if not expected or not found or expected == found:
        return None
    if check.diagnosis == "wrong_case_path" or expected.lower() == found.lower():
        tmp = found + ".tmp"
        command = f"git mv {sh_path(found)} {sh_path(tmp)}\ngit mv {sh_path(tmp)} {sh_path(expected)}"
        summary = f"Rename {found} to {expected} (two steps, so case-insensitive file systems see the change), then commit."
    else:
        command = f"git mv {sh_path(found)} {sh_path(expected)}"
        summary = f"Move {found} to {expected} with git mv, then commit."
    return Fix(summary=summary, file=found, after=command, confidence="high")


@_builder("untracked_file")
def _fix_untracked(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    path = id_suffix(check, "git:untracked:") or subject_path(check)
    if not path:
        return None
    return Fix(summary=f"Track the file: git add {sh_path(path)}, then commit.", file=path,
               after=f"git add {sh_path(path)}", confidence="high")


@_builder("forbidden_builtin")
def _fix_forbidden_builtin(check: CheckResult, sources: Sources, modules: Modules) -> Fix | None:
    name = constraint_name(check)
    if not name:
        return None
    idea = BUILTIN_HINTS.get(name, "write the logic yourself with conditions and loops")
    return Fix(summary=f"Replace {name}() with your own logic: {idea}.", file=check.file, confidence="low")
