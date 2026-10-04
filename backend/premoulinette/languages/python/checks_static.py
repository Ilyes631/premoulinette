"""Deterministic static checks built on :mod:`premoulinette.languages.python.static` (never executes code).

Conventions (see docs/ARCHITECTURE.md):
* ``file_map``: spec path -> actual snapshot-relative path (or None when the file is missing).
* ``CheckResult.file`` is the SPEC path; ``location.file`` / ``evidence.code.file`` the ACTUAL path.
* Bonus exercises never block: their failures get ``status="bonus"``, ``mandatory=False``, ``bonus=True``.
* Every located issue carries ``evidence.code`` (source excerpt, +-2 lines, highlighted lines).

Each public function also accepts an optional ``sources`` mapping (actual path -> source text) used
for code excerpts; without it the source lines remembered by ``static.analyze_*`` are used.
"""
from __future__ import annotations

import ast
import difflib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from premoulinette.languages.python.builtins_catalog import BUILTIN_EXCEPTIONS, BUILTIN_FUNCTIONS, BYPASS_BUILTINS
from premoulinette.languages.python.static import source_lines_of, split_source_lines
from premoulinette.languages.python.static_models import CallSite, FunctionInfo, ModuleInfo, ParamInfo
from premoulinette.results.models import Category, CheckResult, CodeExcerpt, Evidence, Location, Severity, Status
from premoulinette.spec.models import (
    Constraints,
    ExerciseSpec,
    FileRequirement,
    FunctionSpec,
    Origin,
    PracticalSpec,
)

__all__ = ["check_syntax", "check_functions", "check_constraints", "check_import_side_effects"]

Modules = Mapping[str, ModuleInfo]
FileMap = Mapping[str, "str | None"]
Sources = Mapping[str, str] | None

NEAR_MISS_CUTOFF = 0.8
_CONTEXT = 2
_MAX_EXCERPT = 15
_EFFECT_KINDS = ("print", "input", "call")

_CONSTRUCT_LABELS = {
    "for": "for loops", "while": "while loops", "loop": "loops (for / while)", "comprehension": "comprehensions",
    "lambda": "lambda functions", "recursion": "recursion", "try": "try/except blocks", "global": "global statements",
    "class": "classes", "import": "imports", "with": "with statements", "yield": "generators (yield)",
    "fstring": "f-strings", "walrus": "the walrus operator (:=)", "match": "match statements",
}


# ------------------------------------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Mode:
    mandatory: bool
    bonus: bool

    @property
    def failed(self) -> Status:
        return "fail" if self.mandatory else ("bonus" if self.bonus else "warning")


def _ex_mode(ex: ExerciseSpec) -> _Mode:
    return _Mode(mandatory=ex.required and not ex.bonus, bonus=ex.bonus)


def _file_mode(req: FileRequirement) -> _Mode:
    return _Mode(mandatory=req.required and not req.bonus, bonus=req.bonus)


def _base(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _lines_word(lines: list[int]) -> str:
    uniq = sorted(set(lines))
    if not uniq:
        return "no line"
    if len(uniq) == 1:
        return f"line {uniq[0]}"
    if len(uniq) > 8:
        return "lines " + ", ".join(str(n) for n in uniq[:8]) + ", …"
    return "lines " + ", ".join(str(n) for n in uniq[:-1]) + f" and {uniq[-1]}"


def _where(fn: str | None) -> str:
    return f"in {fn}()" if fn else "at module level"


def _source_lines(mod: ModuleInfo, sources: Sources) -> list[str] | None:
    if sources is not None and mod.path in sources:
        return split_source_lines(sources[mod.path])
    return source_lines_of(mod)


def _excerpt(lines: list[str] | None, file: str, highlight: list[int]) -> CodeExcerpt | None:
    """Source window around the highlighted lines (+-2 lines of context, at most 15 lines)."""
    if not lines:
        return None
    n = len(lines)
    marks = sorted({min(max(1, h), n) for h in highlight if isinstance(h, int)})
    if not marks:
        return None
    start = max(1, marks[0] - _CONTEXT)
    end = min(n, marks[-1] + _CONTEXT)
    if end - start + 1 > _MAX_EXCERPT:
        end = start + _MAX_EXCERPT - 1
    return CodeExcerpt(file=file, start_line=start, lines=lines[start - 1:end],
                       highlight=[h for h in marks if start <= h <= end])


def _evidence(src_lines: list[str] | None, file: str, highlight: list[int], /, **details: object) -> Evidence:
    return Evidence(code=_excerpt(src_lines, file, highlight), details={k: v for k, v in details.items() if v is not None})


def _check(
    cid: str, category: Category, status: Status, title: str, message: str, mode: _Mode, *,
    severity: Severity | None = None, diagnosis: str | None = None, ex: ExerciseSpec | None = None,
    function: str | None = None, file: str | None = None, location: Location | None = None,
    origin: Origin | None = None, blocked_by: str | None = None, evidence: Evidence | None = None,
) -> CheckResult:
    return CheckResult(
        id=cid, category=category, status=status, severity=None if status == "pass" else severity, title=title,
        message=message, diagnosis=diagnosis, exercise_id=ex.id if ex else None, function=function, file=file,
        location=location, origin=origin.model_copy(deep=True) if origin else Origin(), mandatory=mode.mandatory,
        bonus=mode.bonus, blocked_by=blocked_by, evidence=evidence, tags=["static"],
    )


def _norm_annotation(text: str | None) -> str:
    if not text:
        return ""
    s = "".join(text.split())
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1]
    s = re.sub(r"\btyping\.", "", s)
    return re.sub(r"\b(List|Dict|Tuple|Set|FrozenSet|Type)\b", lambda m: m.group(1).lower(), s)


def _literal(src: str | None) -> object:
    if src is None:
        return None
    try:
        return ast.literal_eval(src)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def _render_params(params: list[ParamInfo]) -> str:
    parts: list[str] = []
    has_var = any(p.kind == "vararg" for p in params)
    star_done = False
    posonly = [p for p in params if p.kind == "posonly"]
    for p in params:
        if p.kind == "kwonly" and not has_var and not star_done:
            parts.append("*")
            star_done = True
        text = p.name
        if p.kind == "vararg":
            text = "*" + text
        elif p.kind == "varkw":
            text = "**" + text
        if p.annotation:
            text += f": {p.annotation}"
        if p.default is not None:
            text += f" = {p.default}" if p.annotation else f"={p.default}"
        parts.append(text)
        if posonly and p is posonly[-1]:
            parts.append("/")
    return ", ".join(parts)


def _render_def(info: FunctionInfo) -> str:
    ret = f" -> {info.return_annotation}" if info.return_annotation else ""
    return f"def {info.name}({_render_params(info.params)}){ret}"


def _near_miss(name: str, candidates: list[str]) -> str | None:
    lowered: dict[str, str] = {}
    for c in candidates:
        lowered.setdefault(c.lower(), c)
    if name.lower() in lowered:
        return lowered[name.lower()]
    close = difflib.get_close_matches(name.lower(), list(lowered), n=1, cutoff=NEAR_MISS_CUTOFF)
    return lowered[close[0]] if close else None


def _groups(spec: PracticalSpec) -> dict[str, list[ExerciseSpec]]:
    groups: dict[str, list[ExerciseSpec]] = {}
    for ex in spec.exercises:
        groups.setdefault(ex.file_path, []).append(ex)
    return groups


def _primary(group: list[ExerciseSpec]) -> ExerciseSpec:
    return next((e for e in group if not e.bonus), group[0])


def _attribution(ex: ExerciseSpec, group: list[ExerciseSpec]) -> Callable[[str | None], bool]:
    """Which code of a shared file belongs to ``ex`` (keyed by enclosing top-level function)."""
    if len(group) == 1:
        return lambda fn: True
    own = {f.name for f in ex.functions}
    others = {f.name for e in group if e is not ex for f in e.functions} - own
    if ex is _primary(group):
        return lambda fn: fn not in others
    return lambda fn: fn is not None and fn in own


# ------------------------------------------------------------------------------------------------
# Syntax
# ------------------------------------------------------------------------------------------------


def check_syntax(modules: Modules, file_map: FileMap, spec: PracticalSpec, *, sources: Sources = None) -> list[CheckResult]:
    """One ``syntax:<spec_path>`` check per expected .py file found (+ info for other unparsable .py files)."""
    checks: list[CheckResult] = []
    mapped: set[str] = set()
    for req in spec.expected_files():
        if req.kind != "file" or not req.path.endswith(".py"):
            continue
        actual = file_map.get(req.path)
        mod = modules.get(actual) if actual else None
        if actual is None or mod is None:
            continue
        mapped.add(actual)
        checks.append(_syntax_check(f"syntax:{req.path}", req.path, mod, _file_mode(req), req.origin, sources))
    ids = {c.id for c in checks}
    for path in sorted(modules):
        mod = modules[path]
        if path in mapped or mod.ok or f"syntax:{path}" in ids:
            continue
        check = _syntax_check(f"syntax:{path}", path, mod, _Mode(False, False), None, sources)
        check.status = "info"
        check.severity = "minor"
        check.message += " This file is not required by the subject, but it cannot be imported either."
        checks.append(check)
    return checks


def _syntax_check(cid: str, spec_path: str, mod: ModuleInfo, mode: _Mode, origin: Origin | None,
                  sources: Sources) -> CheckResult:
    actual = mod.path
    name = _base(actual)
    if mod.ok:
        return _check(cid, "syntax", "pass", "Valid Python syntax", f"{name} compiles without syntax errors.", mode,
                      file=spec_path, location=Location(file=actual), origin=origin)
    lines = _source_lines(mod, sources)
    if mod.encoding_error is not None:
        return _check(
            cid, "syntax", mode.failed, "File encoding error",
            f"{name} cannot be read as Python source: {mod.encoding_error} Python cannot run it, so none of its "
            f"tests can run.", mode, severity="critical", diagnosis="encoding_error", file=spec_path,
            location=Location(file=actual), origin=origin, evidence=Evidence(details={"error": mod.encoding_error}),
        )
    err = mod.syntax_error
    kind = err.kind if err else "SyntaxError"
    indentation = kind in ("IndentationError", "TabError")
    msg = err.message if err else "invalid syntax"
    where = ""
    if err and err.line:
        where = f", line {err.line}" + (f", column {err.col}" if err.col else "")
    title = "Indentation error" if indentation else "Syntax error"
    message = (f"{kind} in {name}{where}: {msg}. Python cannot run this file, so none of its tests can run.")
    location = Location(file=actual, line=err.line if err else None,
                        col=(err.col - 1) if err and err.col else None)
    evidence = _evidence(lines, actual, [err.line] if err and err.line else [], kind=kind, message=msg,
                         line=err.line if err else None, col=err.col if err else None, text=err.text if err else None)
    return _check(cid, "syntax", mode.failed, title, message, mode, severity="critical",
                  diagnosis="indentation_error" if indentation else "syntax_error", file=spec_path,
                  location=location, origin=origin, evidence=evidence)


# ------------------------------------------------------------------------------------------------
# Functions: presence, signature, return-vs-print
# ------------------------------------------------------------------------------------------------


def check_functions(spec: PracticalSpec, modules: Modules, file_map: FileMap, *, sources: Sources = None) -> list[CheckResult]:
    checks: list[CheckResult] = []
    groups = _groups(spec)
    for ex in spec.exercises:
        if not ex.functions:
            continue
        actual = file_map.get(ex.file_path)
        mod = modules.get(actual) if actual else None
        expected_here = {f.name for e in groups[ex.file_path] for f in e.functions}
        for fn in ex.functions:
            checks.extend(_function_checks(ex, fn, actual, mod, modules, expected_here, sources))
    return checks


def _function_checks(ex: ExerciseSpec, fn: FunctionSpec, actual: str | None, mod: ModuleInfo | None,
                     modules: Modules, expected_here: set[str], sources: Sources) -> list[CheckResult]:
    mode = _ex_mode(ex)
    cid = f"function:{ex.id}:{fn.name}"
    common = {"ex": ex, "function": fn.name, "file": ex.file_path, "origin": fn.origin}
    expected_sig = fn.signature.render()

    if mod is None:
        if mode.bonus:
            return [_check(cid, "functions", "bonus", "Bonus not implemented",
                           f"Bonus function {fn.name}() is not implemented: {ex.file_path} was not found (optional).",
                           mode, diagnosis="bonus_not_implemented", blocked_by=f"structure:file:{ex.file_path}", **common)]
        return [_check(cid, "functions", "skipped", "Function not checked",
                       f"{fn.name}() could not be checked because {ex.file_path} was not found.", mode,
                       blocked_by=f"structure:file:{ex.file_path}", **common)]
    name = _base(mod.path)
    if not mod.ok:
        return [_check(cid, "functions", "skipped", "Function not checked",
                       f"{fn.name}() could not be checked because {name} does not compile (fix the "
                       f"{'encoding' if mod.encoding_error else 'syntax'} error first).", mode,
                       blocked_by=f"syntax:{ex.file_path}", **common)]

    lines = _source_lines(mod, sources)
    info = mod.function(fn.name)
    if info is None:
        return [_missing_function_check(cid, ex, fn, mod, modules, expected_here, lines, sources, mode, common)]

    out = [_check(cid, "functions", "pass", "Function found", f"{fn.name}() is defined in {name} (line {info.line}).",
                  mode, location=Location(file=mod.path, line=info.line, end_line=info.end_line), **common)]
    out.append(_signature_check(ex, fn, info, mod, lines, mode, common, expected_sig))
    returns = _returns_check(ex, fn, info, mod, lines, mode, common)
    if returns is not None:
        out.append(returns)
    return out


def _missing_function_check(cid: str, ex: ExerciseSpec, fn: FunctionSpec, mod: ModuleInfo, modules: Modules,
                            expected_here: set[str], lines: list[str] | None, sources: Sources, mode: _Mode,
                            common: dict) -> CheckResult:
    name = _base(mod.path)
    defined = [f.name for f in mod.functions]

    nested = next((f for f in mod.nested_functions if f.name == fn.name), None)
    if nested is not None:
        return _check(
            cid, "functions", mode.failed, "Function is nested",
            f"{fn.name}() is defined inside another function or class (line {nested.line}) in {name}: the grader "
            f"can only call functions defined at the top level of the file. Move it out (no indentation).",
            mode, severity="critical", diagnosis="nested_function",
            location=Location(file=mod.path, line=nested.line, end_line=nested.end_line),
            evidence=_evidence(lines, mod.path, [nested.line], found_line=nested.line), **common)

    near = _near_miss(fn.name, [d for d in defined if d not in expected_here])
    if near is not None:
        found = mod.function(near)
        line = found.line if found else None
        return _check(
            cid, "functions", mode.failed, "Wrong function name",
            f"Found def {near}() on line {line} — did you mean {fn.name}()? The grader calls {fn.name}() by its "
            f"exact name, so it will not find your function.",
            mode, severity="critical", diagnosis="wrong_function_name",
            location=Location(file=mod.path, line=line, end_line=found.end_line if found else None),
            evidence=_evidence(lines, mod.path, [line] if line else [], found=near, expected_name=fn.name,
                               found_line=line, defined=defined),
            **common)

    elsewhere = [(path, m.function(fn.name)) for path, m in sorted(modules.items())
                 if path != mod.path and m.ok and m.function(fn.name) is not None]
    if elsewhere:
        other_path, other = elsewhere[0]
        assert other is not None
        other_mod = modules[other_path]
        return _check(
            cid, "functions", mode.failed, "Function in the wrong file",
            f"{fn.name}() is defined in {other_path} (line {other.line}), but the subject expects it in "
            f"{ex.file_path}. The grader imports {_base(ex.file_path)} and will not find it.",
            mode, severity="critical", diagnosis="function_in_wrong_file",
            location=Location(file=other_path, line=other.line, end_line=other.end_line),
            evidence=_evidence(_source_lines(other_mod, sources), other_path, [other.line], found_path=other_path,
                               expected_path=ex.file_path, found_line=other.line,
                               also_in=[p for p, _ in elsewhere[1:]] or None),
            **common)

    if mode.bonus:
        return _check(cid, "functions", "bonus", "Bonus not implemented",
                      f"Bonus function {fn.name}() is not implemented in {name} (optional).", mode,
                      diagnosis="bonus_not_implemented", location=Location(file=mod.path),
                      evidence=Evidence(details={"defined": defined}), **common)
    shown = ", ".join(f"{d}()" for d in defined) if defined else "no function at all"
    return _check(
        cid, "functions", mode.failed, "Missing function",
        f"Function {fn.name}() was not found in {name} (it defines {shown}). Expected: {fn.signature.render()}.",
        mode, severity="critical", diagnosis="missing_function", location=Location(file=mod.path),
        evidence=Evidence(details={"defined": defined, "expected_signature": fn.signature.render()}), **common)


def _signature_check(ex: ExerciseSpec, fn: FunctionSpec, info: FunctionInfo, mod: ModuleInfo,
                     lines: list[str] | None, mode: _Mode, common: dict, expected_sig: str) -> CheckResult:
    cid = f"signature:{ex.id}:{fn.name}"
    spec_params = fn.signature.params
    n = len(spec_params)
    n_required = sum(1 for p in spec_params if p.default is None)
    positional = [p for p in info.params if p.kind in ("posonly", "positional")]
    required_pos = [p for p in positional if p.default is None]
    has_var = any(p.kind == "vararg" for p in info.params)
    required_kw = [p for p in info.params if p.kind == "kwonly" and p.default is None]
    actual_sig = _render_def(info)
    location = Location(file=mod.path, line=info.line)
    evidence = _evidence(lines, mod.path, [info.line], expected_signature=expected_sig, actual_signature=actual_sig)

    callable_like_subject = len(required_pos) <= n_required and (n <= len(positional) or has_var) and not required_kw
    if not callable_like_subject:
        detail = f"the subject's version takes {n} parameter{'s' if n != 1 else ''}"
        if required_kw:
            detail += f", yours requires keyword-only parameter(s) {', '.join(p.name for p in required_kw)}"
        else:
            detail += f", yours takes {len(positional)}"
        evidence.details["issues"] = [detail]
        return _check(cid, "functions", mode.failed, "Wrong number of parameters",
                      f"{fn.name}() cannot be called like in the subject: {detail}. Expected {expected_sig}, "
                      f"found {actual_sig}.", mode, severity="critical", diagnosis="wrong_param_count",
                      location=location, evidence=evidence, **common)

    name_issues = [f"parameter {i + 1} is named '{act.name}' instead of '{exp.name}'"
                   for i, (exp, act) in enumerate(zip(spec_params, positional)) if exp.name != act.name]
    ann_issues: list[str] = []
    for exp, act in zip(spec_params, positional):
        if exp.annotation and _norm_annotation(exp.annotation) != _norm_annotation(act.annotation):
            ann_issues.append(f"'{act.name}' is annotated {act.annotation or '(nothing)'} instead of {exp.annotation}")
    if fn.signature.return_annotation and (
            _norm_annotation(fn.signature.return_annotation) != _norm_annotation(info.return_annotation)):
        ann_issues.append(f"the return annotation is {info.return_annotation or '(missing)'} instead of "
                          f"{fn.signature.return_annotation}")
    issues = name_issues + ann_issues
    if issues:
        evidence.details["issues"] = issues
    if name_issues:
        return _check(cid, "functions", mode.failed, "Parameter names differ from the subject",
                      f"Parameter names of {fn.name}() differ from the subject: {'; '.join(issues)}. "
                      f"Expected {expected_sig}.", mode, severity="minor", diagnosis="wrong_param_names",
                      location=location, evidence=evidence, **common)
    if ann_issues:
        return _check(cid, "functions", "warning", "Type annotations differ from the subject",
                      f"Type annotations of {fn.name}() differ from the subject: {'; '.join(ann_issues)}. "
                      f"Expected {expected_sig}.", mode, severity="style", diagnosis="wrong_annotation",
                      location=location, evidence=evidence, **common)
    return _check(cid, "functions", "pass", "Signature matches the subject",
                  f"{fn.name}() has the expected signature: {expected_sig}.", mode, location=location,
                  evidence=evidence, **common)


def _expects_value(fn: FunctionSpec) -> bool:
    """Only claim "must return" when the subject shows a returned value (avoids false positives on
    functions whose job is to print)."""
    if fn.signature.return_annotation not in (None, "None"):
        return True
    if fn.reference or any(r.returns not in (None, "None") for r in fn.rules):
        return True
    return any(t.expected_return not in (None, "None") for t in fn.tests)


def _returns_check(ex: ExerciseSpec, fn: FunctionSpec, info: FunctionInfo, mod: ModuleInfo, lines: list[str] | None,
                   mode: _Mode, common: dict) -> CheckResult | None:
    if not fn.must_return or not _expects_value(fn):
        return None
    if any(c.name == "yield" and c.in_function == fn.name for c in mod.constructs):
        return None   # generator function: returns an iterator, not checked statically
    cid = f"returns:{ex.id}:{fn.name}"
    expected_type = _norm_annotation(fn.signature.return_annotation)

    if expected_type == "bool":
        bad = [r for r in info.returns if r.value_kind == "constant" and r.constant_type == "str"
               and _literal(r.value_src) in ("True", "False")]
        if bad:
            first = bad[0]

            def stmt(line: int, value_src: str | None) -> str:
                if lines and 0 < line <= len(lines) and lines[line - 1].strip().startswith("return"):
                    return lines[line - 1].strip()
                return f"return {value_src}"

            shown = " and ".join(f"line {r.line} has `{stmt(r.line, r.value_src)}`" for r in bad)
            return _check(
                cid, "functions", mode.failed, "Returns a string instead of a boolean",
                f"{fn.name}() must return a bool (True / False), but {shown}: quoted values are strings, not "
                f"booleans. Remove the quotes.", mode, severity="major", diagnosis="str_instead_of_bool",
                location=Location(file=mod.path, line=first.line),
                evidence=_evidence(lines, mod.path, [r.line for r in bad], lines=[r.line for r in bad],
                                   values=[r.value_src for r in bad], expected_type="bool"),
                **common)

    if not info.has_value_return:
        if info.prints:
            return _check(
                cid, "functions", mode.failed, "Prints instead of returning",
                f"{fn.name}() prints its result ({_lines_word(info.prints)}) but never returns a value: the grader "
                f"receives None. Use return instead of print().", mode, severity="major",
                diagnosis="prints_instead_of_returns", location=Location(file=mod.path, line=info.prints[0]),
                evidence=_evidence(lines, mod.path, list(info.prints), print_lines=list(info.prints),
                                   expected_type=expected_type or None),
                **common)
        return _check(
            cid, "functions", "warning", "No value returned",
            f"{fn.name}() has no return statement with a value: calling it gives None, but the subject expects "
            f"{('a ' + expected_type) if expected_type else 'a value'}.", mode, severity="major",
            diagnosis="returns_none", location=Location(file=mod.path, line=info.line),
            evidence=_evidence(lines, mod.path, [info.line], expected_type=expected_type or None),
            **common)
    return _check(cid, "functions", "pass", "Returns its result",
                  f"{fn.name}() returns its result with a return statement.", mode,
                  location=Location(file=mod.path, line=info.line), **common)


# ------------------------------------------------------------------------------------------------
# Constraints
# ------------------------------------------------------------------------------------------------


@dataclass
class _Ctx:
    ex: ExerciseSpec
    cons: Constraints
    mod: ModuleInfo
    lines: list[str] | None
    mode: _Mode
    mine: Callable[[str | None], bool]

    @property
    def name(self) -> str:
        return _base(self.mod.path)

    def fail(self, rule: str, key: str, title: str, message: str, diagnosis: str, line_numbers: list[int],
             severity: Severity = "critical", first_col: int | None = None, **details: object) -> CheckResult:
        first = line_numbers[0] if line_numbers else None
        if self.mode.bonus:
            message += " (Bonus exercise: this does not block your submission.)"
        return _check(
            f"constraint:{self.ex.id}:{rule}:{key}", "constraints", self.mode.failed, title, message, self.mode,
            severity=severity, diagnosis=diagnosis, ex=self.ex, file=self.ex.file_path,
            location=Location(file=self.mod.path, line=first, col=first_col) if first else Location(file=self.mod.path),
            origin=self.cons.origin,
            evidence=_evidence(self.lines, self.mod.path, line_numbers, lines=sorted(set(line_numbers)) or None,
                               **details),
        )

    def ok(self, rule: str, key: str, title: str, message: str) -> CheckResult:
        return _check(f"constraint:{self.ex.id}:{rule}:{key}", "constraints", "pass", title, message, self.mode,
                      ex=self.ex, file=self.ex.file_path, location=Location(file=self.mod.path),
                      origin=self.cons.origin)


def _group_calls(calls: list[CallSite]) -> dict[str, list[CallSite]]:
    out: dict[str, list[CallSite]] = {}
    for c in sorted(calls, key=lambda c: (c.line, c.col)):
        out.setdefault(c.name, []).append(c)
    return out


def _uses_text(uses: list[CallSite]) -> str:
    fns = sorted({u.in_function for u in uses}, key=lambda f: (f is not None, f or ""))
    where = ", ".join(_where(f) for f in fns)
    times = f"{len(uses)} times " if len(uses) > 1 else ""
    return f"{times}{where} ({_lines_word([u.line for u in uses])})"


def check_constraints(spec: PracticalSpec, modules: Modules, file_map: FileMap, *, sources: Sources = None) -> list[CheckResult]:
    checks: list[CheckResult] = []
    groups = _groups(spec)
    for ex in spec.exercises:
        cons = spec.effective_constraints(ex)
        if cons.is_empty():
            continue
        actual = file_map.get(ex.file_path)
        mod = modules.get(actual) if actual else None
        if mod is None or not mod.ok:
            continue   # missing file / syntax error are reported elsewhere
        group = groups[ex.file_path]
        if ex is not _primary(group) and not any(mod.function(f.name) for f in ex.functions):
            continue   # nothing of this (bonus) exercise is implemented in the shared file
        ctx = _Ctx(ex, cons, mod, _source_lines(mod, sources), _ex_mode(ex), _attribution(ex, group))
        checks.extend(_builtin_checks(ctx))
        checks.extend(_import_checks(ctx))
        checks.extend(_method_checks(ctx))
        checks.extend(_construct_checks(ctx))
    return checks


def _builtin_checks(ctx: _Ctx) -> list[CheckResult]:
    cons, out = ctx.cons, []
    if not cons.forbidden_builtins and cons.allowed_builtins is None:
        return out
    calls = [c for c in ctx.mod.calls if ctx.mine(c.in_function)]
    direct = [c for c in calls if c.kind == "builtin" and not c.referenced_only]
    refs = [c for c in calls if c.kind == "builtin" and c.referenced_only]
    forbidden = set(cons.forbidden_builtins)
    reported: set[str] = set()

    if forbidden:
        by_name = _group_calls([c for c in direct if c.name in forbidden])
        for name, uses in by_name.items():
            reported.add(name)
            extra_refs = [r for r in refs if r.name == name]
            all_lines = [u.line for u in uses] + [r.line for r in extra_refs]
            out.append(ctx.fail(
                "forbidden_builtin", name, f"Forbidden builtin {name}()",
                f"{name}() is forbidden by the subject, but {ctx.name} calls it {_uses_text(uses)}.",
                "forbidden_builtin", all_lines, first_col=uses[0].col, name=name,
                functions=sorted({u.in_function or "<module>" for u in uses}), count=len(uses)))
        if not by_name:
            out.append(ctx.ok("forbidden_builtin", "*", "No forbidden builtin",
                              f"{ctx.name} calls none of the forbidden builtins ({', '.join(cons.forbidden_builtins)})."))

    if cons.allowed_builtins is not None:
        allowed = set(cons.allowed_builtins)
        bad = [c for c in direct if c.name not in allowed and c.name not in forbidden and c.name not in BUILTIN_EXCEPTIONS]
        bad += [r for r in refs if r.name not in allowed and r.name not in forbidden and r.name in BUILTIN_FUNCTIONS
                and r.name not in BYPASS_BUILTINS]
        by_name = _group_calls(bad)
        allowed_text = ", ".join(cons.allowed_builtins) if cons.allowed_builtins else "none"
        for name, uses in by_name.items():
            reported.add(name)
            only_refs = all(u.referenced_only for u in uses)
            verb = "uses it without calling it" if only_refs else "calls it"
            out.append(ctx.fail(
                "builtin_not_allowed", name, f"Builtin {name}() is not authorized",
                f"{name}() is not in the list of authorized builtins ({allowed_text}), but {ctx.name} {verb} "
                f"{_uses_text(uses)}.", "builtin_not_allowed", [u.line for u in uses], first_col=uses[0].col,
                name=name, allowed=list(cons.allowed_builtins), count=len(uses)))
        if not by_name:
            out.append(ctx.ok("builtin_not_allowed", "*", "Only authorized builtins",
                              f"{ctx.name} only uses authorized builtins ({allowed_text})."))

    out.extend(_bypass_checks(ctx, calls, direct, refs, forbidden, reported))
    return out


def _bypass_checks(ctx: _Ctx, calls: list[CallSite], direct: list[CallSite], refs: list[CallSite],
                   forbidden: set[str], reported: set[str]) -> list[CheckResult]:
    items: dict[str, tuple[list[int], str]] = {}

    def add(key: str, line: int, why: str) -> None:
        lines, _ = items.get(key, ([], why))
        lines.append(line)
        items[key] = (lines, why)

    for c in calls:
        if c.name == "__builtins__" and c.referenced_only:
            add("__builtins__", c.line, "accesses __builtins__, which gives access to every builtin")
    for s in ctx.mod.strings:
        if s.value == "__builtins__" and ctx.mine(s.in_function):
            add("__builtins__", s.line, "refers to \"__builtins__\", which gives access to every builtin")
    for imp in ctx.mod.imports:
        if ctx.mine(imp.in_function) and imp.module.split(".")[0] == "builtins":
            add("builtins", imp.line, "imports the builtins module, which gives access to every builtin")
    for c in direct:
        if c.name in BYPASS_BUILTINS and c.name not in reported:
            add(c.name, c.line, f"calls {c.name}(), which can run arbitrary code and bypass the builtin restrictions")
    for r in refs:
        if r.name in forbidden and r.name not in reported:
            add(r.name, r.line, f"uses the forbidden builtin {r.name} without calling it directly "
                                f"(e.g. f = {r.name} or map({r.name}, ...)): this is still a use of {r.name}")
    out = []
    for key, (lines, why) in items.items():
        out.append(ctx.fail("builtin_bypass", key, "Builtin restriction bypass",
                            f"{ctx.name} {why} ({_lines_word(lines)}).", "builtin_bypass", sorted(lines), name=key))
    return out


def _import_checks(ctx: _Ctx) -> list[CheckResult]:
    cons = ctx.cons
    if cons.allowed_imports is None and not cons.forbidden_imports:
        return []

    def matches(module: str, patterns: list[str]) -> bool:
        return any(module == p or module.startswith(p + ".") for p in patterns)

    bad: dict[str, list] = {}
    for imp in ctx.mod.imports:
        if not ctx.mine(imp.in_function):
            continue
        not_allowed = cons.allowed_imports is not None and not matches(imp.module, cons.allowed_imports)
        if not_allowed or matches(imp.module, cons.forbidden_imports):
            bad.setdefault(imp.module, []).append(imp)
    out = []
    for module, imps in bad.items():
        first = imps[0]
        stmt = f"from {module} import {', '.join(first.names)}" if first.names else f"import {module}"
        if matches(module, cons.forbidden_imports):
            reason = "the subject explicitly forbids this module"
        elif not cons.allowed_imports:
            reason = "the subject forbids every import"
        else:
            reason = f"the subject only allows: {', '.join(cons.allowed_imports)}"
        out.append(ctx.fail("import", module, f"Forbidden import {module}",
                            f"{stmt} ({_lines_word([i.line for i in imps])}) is not allowed: {reason}.",
                            "forbidden_import", [i.line for i in imps], module=module, statement=stmt))
    if not bad:
        if cons.allowed_imports is not None and not cons.allowed_imports:
            msg = f"{ctx.name} imports nothing, as required."
        else:
            msg = f"{ctx.name} only imports authorized modules."
        out.append(ctx.ok("import", "*", "No forbidden import", msg))
    return out


def _method_checks(ctx: _Ctx) -> list[CheckResult]:
    forbidden = set(ctx.cons.forbidden_methods)
    if not forbidden:
        return []
    uses = [c for c in ctx.mod.calls if c.kind == "method" and c.name in forbidden and ctx.mine(c.in_function)]
    out = []
    for name, group in _group_calls(uses).items():
        out.append(ctx.fail("method", name, f"Forbidden method .{name}()",
                            f".{name}() is forbidden by the subject, but {ctx.name} calls it {_uses_text(group)}.",
                            "forbidden_method", [u.line for u in group], first_col=group[0].col, method=name))
    if not uses:
        out.append(ctx.ok("method", "*", "No forbidden method",
                          f"{ctx.name} calls none of the forbidden methods ({', '.join(ctx.cons.forbidden_methods)})."))
    return out


def _construct_names(construct: str) -> set[str]:
    return {"for", "while"} if construct == "loop" else {construct}


def _construct_checks(ctx: _Ctx) -> list[CheckResult]:
    out: list[CheckResult] = []
    used = [u for u in ctx.mod.constructs if ctx.mine(u.in_function)]
    if ctx.cons.forbidden_constructs:
        any_bad = False
        for construct in ctx.cons.forbidden_constructs:
            hits = [u for u in used if u.name in _construct_names(construct)]
            if not hits:
                continue
            any_bad = True
            label = _CONSTRUCT_LABELS.get(construct, construct)
            out.append(ctx.fail("construct", construct, f"Forbidden construct: {construct}",
                                f"{label[0].upper() + label[1:]} are forbidden by the subject, but {ctx.name} uses "
                                f"them ({_lines_word([u.line for u in hits])}).", "forbidden_construct",
                                [u.line for u in hits], construct=construct))
        if not any_bad:
            out.append(ctx.ok("construct", "*", "No forbidden construct",
                              f"{ctx.name} uses none of the forbidden constructs "
                              f"({', '.join(ctx.cons.forbidden_constructs)})."))
    for construct in ctx.cons.required_constructs:
        hits = [u for u in used if u.name in _construct_names(construct)]
        label = _CONSTRUCT_LABELS.get(construct, construct)
        if hits:
            out.append(ctx.ok("required_construct", construct, f"Required construct used: {construct}",
                              f"{ctx.name} uses {label} as required ({_lines_word([u.line for u in hits])})."))
        else:
            out.append(ctx.fail("required_construct", construct, f"Required construct missing: {construct}",
                                f"The subject requires {label} in this exercise, but {ctx.name} does not use any.",
                                "missing_required_construct", [], severity="major", construct=construct))
    return out


# ------------------------------------------------------------------------------------------------
# Import side effects (static)
# ------------------------------------------------------------------------------------------------


def check_import_side_effects(spec: PracticalSpec, modules: Modules, file_map: FileMap, *,
                              sources: Sources = None) -> list[CheckResult]:
    """Top-level print/input/calls outside ``if __name__ == "__main__":`` in "functions" exercises."""
    checks: list[CheckResult] = []
    for spec_path, group in _groups(spec).items():
        candidates = [e for e in group if e.kind == "functions" and not e.import_side_effects_allowed]
        if not candidates:
            continue
        ex = _primary(candidates)
        actual = file_map.get(spec_path)
        mod = modules.get(actual) if actual else None
        if mod is None or not mod.ok:
            continue
        mode = _ex_mode(ex)
        name = _base(mod.path)
        cid = f"import_effects:{ex.id}"
        effects = [e for e in mod.top_level_effects if e.kind in _EFFECT_KINDS]
        if not effects:
            checks.append(_check(cid, "runtime", "pass", "No code runs at import",
                                 f"Importing {name} does not print, ask for input or call functions.", mode,
                                 ex=ex, file=spec_path, location=Location(file=mod.path), origin=ex.origin))
            continue
        shown = "; ".join(f"line {e.line}: {e.src}" for e in effects[:3]) + ("; …" if len(effects) > 3 else "")
        kinds = {e.kind for e in effects}
        what = "asks for input" if "input" in kinds else ("prints" if "print" in kinds else "runs code")
        checks.append(_check(
            cid, "runtime", "warning", "Code runs when the file is imported",
            f"{name} {what} when it is imported ({shown}). The grader imports your file to call your functions: "
            f"remove this code or put it under if __name__ == \"__main__\":.", mode, severity="major",
            diagnosis="import_side_effects", ex=ex, file=spec_path,
            location=Location(file=mod.path, line=effects[0].line), origin=ex.origin,
            evidence=_evidence(_source_lines(mod, sources), mod.path, [e.line for e in effects],
                               effects=[e.model_dump() for e in effects], has_main_guard=mod.has_main_guard),
        ))
    return checks
