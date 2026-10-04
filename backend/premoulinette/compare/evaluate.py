"""JobResult -> CheckResult: function tests, script sessions (stdout + input() prompts), import effects.

Severity policy (ARCHITECTURE.md): explicit/derived failing -> ``fail`` (crash/timeout critical,
wrong type/value major, typo/case/whitespace-only string difference minor); heuristic failing ->
``warning`` and not mandatory; bonus exercise failing -> ``bonus``; tests that cannot run ->
``skipped`` + ``blocked_by`` (still mandatory).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

from premoulinette.compare.source_map import (
    ActualPrompt,
    actual_prompts,
    attach_line_sources,
    code_excerpt,
    event_location,
    function_excerpt,
    locate_text,
    return_lines_for,
)
from premoulinette.compare.text_diff import PAIR_RATIO, diff_text, first_hint, line_ratio, only_minor
from premoulinette.compare.values import ValueVerdict, compare_values, runtime_failure
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo
from premoulinette.results.models import (
    Category,
    CheckResult,
    CodeExcerpt,
    DiffLine,
    Evidence,
    ExceptionInfo,
    Location,
    Severity,
    Status,
    TextDiff,
    TranscriptEvent,
    ValueSnapshot,
)
from premoulinette.runner.models import JobResult, RawEvent
from premoulinette.spec.models import ExerciseSpec, FunctionSpec, FunctionTest, PracticalSpec, ScriptTest
from premoulinette.testgen.generate import GeneratedFunctionTest, GeneratedScriptTest

MAX_TRANSCRIPT_EVENTS = 500
Outcome = Literal["pass", "warning", "fail", "skipped"]
_HEURISTIC_SEVERITY: dict[str, Severity] = {"critical": "major", "major": "minor", "minor": "minor", "style": "style"}


class EvalContext(BaseModel):
    """Everything evaluation needs besides the job result.

    ``modules``/``sources`` are keyed by snapshot-relative paths (== ``Location.file``), ``file_map``
    maps spec paths to them. ``blocked`` maps a spec path (or ``"<spec path>::<function>"``) to the id
    of the check that prevents running it. ``results`` (optional) holds every JobResult by job id; it
    lets prompt checks use all sessions even when they are evaluated out of order.
    """

    spec: PracticalSpec
    modules: dict[str, ModuleInfo] = Field(default_factory=dict)
    file_map: dict[str, str | None] = Field(default_factory=dict)
    blocked: dict[str, str] = Field(default_factory=dict)
    sources: dict[str, str] = Field(default_factory=dict)
    results: dict[str, JobResult] = Field(default_factory=dict)
    _sessions: dict[str, JobResult | None] = PrivateAttr(default_factory=dict)

    def actual_path(self, spec_path: str) -> str:
        return self.file_map.get(spec_path) or spec_path

    def module_for(self, spec_path: str) -> ModuleInfo | None:
        for key in (self.file_map.get(spec_path), spec_path):
            if key and key in self.modules:
                return self.modules[key]
        return None

    def source_for(self, spec_path: str) -> str | None:
        for key in (self.file_map.get(spec_path), spec_path):
            if key and key in self.sources:
                return self.sources[key]
        return None

    def blocker(self, spec_path: str, function: str | None = None) -> str | None:
        keys = ([f"{spec_path}::{function}"] if function else []) + [spec_path, self.file_map.get(spec_path) or ""]
        return next((self.blocked[k] for k in keys if k and k in self.blocked), None)


# ------------------------------------------------------------------------------------------------
# Status policy
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Policy:
    bonus: bool
    required: bool
    heuristic: bool

    @classmethod
    def of(cls, ex: ExerciseSpec | None, category: Category) -> _Policy:
        bonus = bool(ex and ex.bonus)
        required = ex.required if ex is not None else True
        return cls(bonus=bonus, required=required and not bonus, heuristic=category == "heuristic_tests")

    def apply(self, outcome: Outcome, severity: Severity | None) -> dict[str, Any]:
        mandatory = self.required and not self.heuristic
        status: Status
        if outcome in ("pass", "skipped"):
            status, severity = outcome, None
        elif outcome == "warning":
            status = "warning"
        elif self.bonus:
            status = "bonus"
        elif self.heuristic:
            status, severity = "warning", _HEURISTIC_SEVERITY.get(severity or "minor", "minor")
        else:
            status = "fail"
        return {"status": status, "severity": severity, "mandatory": mandatory, "bonus": self.bonus}


# ------------------------------------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------------------------------------


def _exception_info(res: JobResult) -> ExceptionInfo | None:
    exc = res.exception
    if exc is None:
        return None
    location = Location(file=exc.file, line=exc.line) if exc.file else None
    return ExceptionInfo(type=exc.type, message=exc.message, traceback=exc.traceback, location=location)


def _call_events(res: JobResult) -> list[RawEvent]:
    """Events of the call itself: a function job also records the module import first."""
    if not res.import_stdout:
        return list(res.events)
    consumed = 0
    for k, ev in enumerate(res.events):
        if consumed >= len(res.import_stdout):
            return list(res.events[k:])
        if ev.kind == "output":
            consumed += len(ev.text)
    return []


def _transcript(res: JobResult) -> list[TranscriptEvent] | None:
    if not res.events:
        return None
    return [TranscriptEvent(kind=e.kind, text=e.text, location=event_location(e))
            for e in res.events[:MAX_TRANSCRIPT_EVENTS]]


def _run_evidence(res: JobResult, evidence: Evidence) -> None:
    evidence.actual_stdout = res.stdout or evidence.actual_stdout
    evidence.stderr = res.stderr or None
    evidence.exit_code = res.exit_code
    evidence.exception = _exception_info(res)
    evidence.timed_out = res.status == "timeout"
    evidence.duration_ms = res.duration_ms
    evidence.transcript = _transcript(res)
    if res.truncated:
        evidence.details["truncated"] = True
    if res.blocked_syscalls:
        evidence.details["blocked_syscalls"] = list(res.blocked_syscalls)


def _line_excerpt(ctx: EvalContext, spec_path: str, location: Location | None, context: int = 3) -> CodeExcerpt | None:
    if location is None or location.line is None:
        return None
    source = ctx.sources.get(location.file) or ctx.source_for(spec_path)
    return code_excerpt(source, location.file, location.line - context, location.line + context, [location.line])


def _skipped(base: dict[str, Any], policy: _Policy, blocker: str | None, evidence: Evidence, reason: str) -> CheckResult:
    message = f"Not run: blocked by {blocker}." if blocker else reason
    return CheckResult(**base, **policy.apply("skipped", None), message=message, blocked_by=blocker, evidence=evidence)


def _session_label(test: ScriptTest) -> str:
    if test.title:
        return test.title
    head, sep, tail = test.id.rpartition("#session")
    return f"Session {tail}" if sep and tail.isdigit() else test.id


# ------------------------------------------------------------------------------------------------
# Function tests
# ------------------------------------------------------------------------------------------------


def _function_spec(ex: ExerciseSpec | None, name: str) -> FunctionSpec | None:
    if ex is None:
        return None
    return next((f for f in ex.functions if f.name == name), None)


def evaluate_function(gen: GeneratedFunctionTest, res: JobResult | None, ctx: EvalContext) -> CheckResult:
    test = gen.test
    ex = ctx.spec.exercise(gen.exercise_id)
    fn = _function_spec(ex, test.function)
    spec_path = ex.file_path if ex else None
    module = ctx.module_for(spec_path) if spec_path else None
    fn_info = module.function(test.function) if module else None
    policy = _Policy.of(ex, gen.category)
    base: dict[str, Any] = {
        "id": f"test:{test.id}", "category": gen.category, "title": test.call_repr(), "exercise_id": gen.exercise_id,
        "function": test.function, "test_id": test.id, "file": spec_path, "origin": test.origin,
    }
    evidence = Evidence(call=test.call_repr(), rule=gen.rule, details={"compare": test.compare})

    blocker = ctx.blocker(spec_path, test.function) if spec_path else None
    if blocker is None and res is None and ex is not None and module is not None and fn_info is None:
        blocker = f"function:{ex.id}:{test.function}"
    if res is None or blocker:
        return _skipped(base, policy, blocker, evidence, "Not run: the test was not executed.")
    if res.status == "harness_error":
        return _skipped(base, policy, None, evidence, f"Not run: harness error ({res.harness_error or 'unknown'}).")

    _run_evidence(res, evidence)
    if test.expected_exception:
        verdict = _expect_exception(test.expected_exception, res)
    else:
        annotation = fn.signature.return_annotation if fn else None
        verdict = compare_values(test.expected_return, test.expected_type, res, compare=test.compare, annotation=annotation)
    evidence.expected_value, evidence.actual_value, evidence.value_diff = verdict.expected, verdict.actual, verdict.value_diff
    evidence.details["verdict"] = verdict.kind

    outcome: Outcome = verdict.status
    severity, diagnosis, message = verdict.severity, verdict.diagnosis, verdict.message
    tags: list[str] = []
    printed_lines: list[int] = []
    call_events = _call_events(res)
    if res.status == "ok" and test.expected_stdout is not None:
        stdout_diff = diff_text(test.expected_stdout, res.stdout)
        attach_line_sources(stdout_diff, call_events, module)
        evidence.expected_stdout, evidence.stdout_diff = test.expected_stdout, stdout_diff
        if not stdout_diff.equal and outcome != "fail":
            outcome, diagnosis = "fail", "stdout_mismatch"
            severity = "minor" if only_minor(list(stdout_diff.kinds)) else "major"
            message = f"The call printed something different from the subject: {stdout_diff.summary}."
    elif res.status == "ok" and res.stdout and fn is not None and not fn.may_print:
        tags.append("unexpected_stdout")
        printed_lines = [e.line for e in call_events if e.kind == "output" and e.line is not None]
        if outcome == "pass":
            outcome, severity, diagnosis = "warning", "major", "unexpected_stdout"
            message = f"{verdict.message} But the function also printed {_preview(res.stdout)}: functions must not print."

    location, highlight = _function_location(res, verdict, diagnosis, fn_info, module, printed_lines)
    if fn_info is not None and module is not None:
        evidence.code = function_excerpt(ctx.sources.get(module.path) or ctx.source_for(spec_path or ""),
                                         module.path, fn_info, highlight)
    return CheckResult(
        **base, **policy.apply(outcome, severity), message=message, diagnosis=diagnosis if outcome != "pass" else None,
        location=location, evidence=evidence, tags=tags,
    )


def _preview(text: str, limit: int = 60) -> str:
    return repr(text if len(text) <= limit else text[: limit - 1] + "…")


def _expect_exception(expected: str, res: JobResult) -> ValueVerdict:
    snaps = {"expected": ValueSnapshot(repr=expected, type="exception")}
    if res.status == "exception" and res.exception is not None and not res.blocked_syscalls:
        actual = ValueSnapshot(repr=f"{res.exception.type}({res.exception.message!r})", type="exception")
        if res.exception.type == expected:
            return ValueVerdict(ok=True, kind="raises", title="Raises the expected exception",
                                message=f"Raised {expected} as expected.", actual=actual, **snaps)
        return ValueVerdict(ok=False, kind="wrong_exception", severity="major", status="fail", diagnosis="exception",
                            title="Wrong exception", actual=actual, **snaps,
                            message=f"Raised {res.exception.type}: {res.exception.message} instead of {expected}.")
    failure = runtime_failure(res, context="call")
    if failure is not None:
        return failure
    shown = res.return_repr if res.return_repr is not None else "None"
    return ValueVerdict(ok=False, kind="no_exception", severity="major", status="fail", diagnosis="wrong_value",
                        title="Expected exception not raised", **snaps,
                        actual=ValueSnapshot(repr=shown, type=res.return_type or "NoneType"),
                        message=f"Returned {shown} instead of raising {expected}.")


def _function_location(
    res: JobResult, verdict: ValueVerdict, diagnosis: str | None, fn_info: FunctionInfo | None,
    module: ModuleInfo | None, printed_lines: list[int],
) -> tuple[Location | None, list[int]]:
    exc = res.exception
    if exc is not None and exc.file and exc.line is not None and verdict.status == "fail":
        inside = fn_info is not None and module is not None and exc.file == module.path \
            and fn_info.line <= exc.line <= fn_info.end_line
        return Location(file=exc.file, line=exc.line), [exc.line] if inside else []
    if fn_info is None or module is None:
        return None, []
    highlight: list[int] = []
    if diagnosis in ("prints_instead_of_returns", "unexpected_stdout"):
        highlight = [ln for ln in (printed_lines or fn_info.prints) if fn_info.line <= ln <= fn_info.end_line] \
            or list(fn_info.prints)
    elif verdict.status != "pass" and verdict.actual is not None:
        highlight = return_lines_for(fn_info, verdict.actual.repr)
    line = highlight[0] if highlight else fn_info.line
    return Location(file=module.path, line=line), highlight


# ------------------------------------------------------------------------------------------------
# Script sessions
# ------------------------------------------------------------------------------------------------


def evaluate_script(gen: GeneratedScriptTest, res: JobResult | None, ctx: EvalContext) -> list[CheckResult]:
    """The session's stdout check, plus the exercise's prompt checks after its last session."""
    ex = ctx.spec.exercise(gen.exercise_id)
    ctx._sessions[gen.test.id] = res
    checks = [_session_check(gen, ex, res, ctx)]
    if ex is not None and ex.script is not None and ex.script.prompts:
        ids = [t.id for t in ex.script.tests]
        if gen.test.id not in ids or gen.test.id == ids[-1]:
            checks.extend(evaluate_prompts(ex, ctx))
    return checks


def _session_check(gen: GeneratedScriptTest, ex: ExerciseSpec | None, res: JobResult | None, ctx: EvalContext) -> CheckResult:
    test = gen.test
    spec_path = ex.file_path if ex else None
    module = ctx.module_for(spec_path) if spec_path else None
    policy = _Policy.of(ex, gen.category)
    label = _session_label(test)
    base: dict[str, Any] = {
        "id": f"test:{test.id}", "category": gen.category, "exercise_id": gen.exercise_id, "test_id": test.id,
        "file": spec_path, "origin": test.origin,
    }
    evidence = Evidence(
        argv=list(test.argv), stdin=test.stdin, expected_stdout=test.expected_stdout,
        expected_steps=[s.model_dump() for s in test.steps] if test.steps else None,
        details={"match": test.match, "expected_exit_code": test.expected_exit_code},
    )
    blocker = ctx.blocker(spec_path) if spec_path else None
    if res is None or blocker:
        return _skipped({**base, "title": f"{label}: not run"}, policy, blocker, evidence, "Not run: the program was not executed.")
    if res.status == "harness_error":
        return _skipped({**base, "title": f"{label}: not run"}, policy, None, evidence,
                        f"Not run: harness error ({res.harness_error or 'unknown'}).")

    _run_evidence(res, evidence)
    diff: TextDiff | None = None
    if test.expected_stdout is not None:
        diff = diff_text(test.expected_stdout, res.stdout)
        attach_line_sources(diff, res.events, module)
        evidence.stdout_diff = diff

    verdict = _script_failure(test, res, label) or _stdout_verdict(test, res, diff, label) or _exit_verdict(test, res, label)
    if verdict is None:
        message = ("The output contains the expected text." if test.match == "contains" else
                   "The output matches the subject exactly.") if diff is not None else "The program ran without error."
        return CheckResult(**base, **policy.apply("pass", None), title=f"{label}: output matches", message=message,
                           evidence=evidence)
    evidence.code = _line_excerpt(ctx, spec_path or "", verdict.location)
    return CheckResult(**base, **policy.apply("fail", verdict.severity), title=verdict.title, message=verdict.message,
                       diagnosis=verdict.diagnosis, location=verdict.location, evidence=evidence)


@dataclass(frozen=True)
class _ScriptVerdict:
    diagnosis: str
    severity: Severity
    title: str
    message: str
    location: Location | None = None


def _exception_location(res: JobResult) -> Location | None:
    exc = res.exception
    return Location(file=exc.file, line=exc.line) if exc is not None and exc.file else None


def _script_failure(test: ScriptTest, res: JobResult, label: str) -> _ScriptVerdict | None:
    exc = res.exception
    if exc is not None and exc.type == "EOFError" and not res.blocked_syscalls:
        n_inputs = test.stdin.count("\n")
        where = f" at line {exc.line}" if exc.line else ""
        pending = actual_prompts(res.events, eof=True, eof_location=_exception_location(res))
        asked = pending[-1].tail()[0]
        asked_text = f" while showing {asked!r}" if asked else ""
        return _ScriptVerdict(
            "eof_error", "critical", f"{label}: asked for more input than provided",
            f"The program called input(){where}{asked_text} but the subject's session only provides "
            f"{n_inputs} line(s) of input (EOFError). Check the order and the number of input() calls.",
            _exception_location(res),
        )
    if exc is not None and exc.type == "SystemExit" and res.status in ("ok", "exception") and not res.blocked_syscalls:
        return None     # sys.exit(): judged by the exit code check
    if res.status == "exception" or (exc is not None and res.status == "ok"):
        if exc is not None and not res.blocked_syscalls:
            where = f" at line {exc.line}" if exc.line else ""
            return _ScriptVerdict("script_crash", "critical", f"{label}: crashed with {exc.type}",
                                  f"The program crashed{where}: {exc.type}: {exc.message}.", _exception_location(res))
    failure = runtime_failure(res, context="script")
    if failure is None:
        return None
    diagnosis = failure.diagnosis or "script_crash"
    if diagnosis in ("exception", "import_crash"):
        diagnosis = "script_crash"
    return _ScriptVerdict(diagnosis, failure.severity or "critical", f"{label}: {failure.title.lower()}",
                          failure.message, _exception_location(res))


def _stdout_verdict(test: ScriptTest, res: JobResult, diff: TextDiff | None, label: str) -> _ScriptVerdict | None:
    if diff is None or test.expected_stdout is None:
        return None
    if test.match == "contains":
        if test.expected_stdout in res.stdout:
            return None
        return _ScriptVerdict("missing_output", "major", f"{label}: expected text not found",
                              f"The output does not contain {_preview(test.expected_stdout)}.")
    if diff.equal:
        return None
    ops = {line.op for line in diff.lines if line.op != "equal"}
    if not res.stdout or ops == {"missing"}:
        diagnosis = "missing_output"
    elif ops == {"extra"}:
        diagnosis = "extra_output"
    else:
        diagnosis = "stdout_mismatch"
    severity: Severity = "minor" if only_minor(list(diff.kinds)) else "major"
    first = next((line for line in diff.lines if line.op != "equal"), None)
    return _ScriptVerdict(diagnosis, severity, f"{label}: {diff.summary}", _mismatch_message(diff, first),
                          first.source if first is not None else None)


def _mismatch_message(diff: TextDiff, first: DiffLine | None) -> str:
    if first is None:
        return f"The output differs from the subject: {diff.summary}."
    src = f" (written by line {first.source.line} of {first.source.file})" if first.source and first.source.line else ""
    if first.op == "changed":
        hints = ", ".join(first.hints) or "different text"
        return f"Output line {first.expected_lineno} differs from the subject: {hints}{src}."
    if first.op == "missing":
        return f"Output line {first.expected_lineno} of the subject is missing: {_preview(first.expected or '')}."
    return f"The program printed an extra line {first.actual_lineno}: {_preview(first.actual or '')}{src}."


def _exit_verdict(test: ScriptTest, res: JobResult, label: str) -> _ScriptVerdict | None:
    expected = test.expected_exit_code
    if expected is None or res.exit_code is None or res.exit_code == expected:
        return None
    return _ScriptVerdict("exit_code", "major", f"{label}: exit code {res.exit_code}",
                          f"The program exited with code {res.exit_code} instead of {expected}.",
                          _exception_location(res))


# ------------------------------------------------------------------------------------------------
# input() prompts
# ------------------------------------------------------------------------------------------------


def _session_prompts(res: JobResult) -> list[ActualPrompt]:
    eof = res.exception is not None and res.exception.type == "EOFError"
    return actual_prompts(res.events, eof=eof, eof_location=_exception_location(res))


def _align_prompts(prompts: list[ActualPrompt], expected_count: int) -> list[ActualPrompt]:
    """Drop prompt-less input() calls when there are more inputs than documented prompts."""
    if len(prompts) > expected_count:
        with_text = [p for p in prompts if p.tail()[0]]
        if len(with_text) >= expected_count:
            return with_text
    return prompts


def evaluate_prompts(ex: ExerciseSpec, ctx: EvalContext) -> list[CheckResult]:
    """``prompt:<exercise_id>:<n>`` checks from the first session that reached the most prompts."""
    assert ex.script is not None
    expected = ex.script.prompts
    policy = _Policy.of(ex, "output")
    module = ctx.module_for(ex.file_path)
    sessions: list[tuple[ScriptTest, JobResult]] = []
    for t in ex.script.tests:
        res = ctx.results.get(t.id) or ctx._sessions.get(t.id)
        if res is not None and res.status != "harness_error":
            sessions.append((t, res))

    def base(n: int, exp: str) -> dict[str, Any]:
        return {"id": f"prompt:{ex.id}:{n}", "category": "output", "title": f"Prompt {n}: {exp!r}",
                "exercise_id": ex.id, "file": ex.file_path, "origin": ex.script.origin}  # type: ignore[union-attr]

    blocker = ctx.blocker(ex.file_path)
    if blocker or not sessions:
        return [_skipped(base(i + 1, exp), policy, blocker, Evidence(), "Not run: no session of the program could run.")
                for i, exp in enumerate(expected)]

    per_session = [(t, r, _align_prompts(_session_prompts(r), len(expected))) for t, r in sessions]
    best_test, best_res, prompts = max(per_session, key=lambda item: len(item[2]))   # first one wins ties
    stopped_early = best_res.status not in ("ok", "exception") or (
        best_res.exception is not None and best_res.exception.type not in ("EOFError", "SystemExit")
    )
    checks: list[CheckResult] = []
    for i, exp in enumerate(expected):
        n = i + 1
        evidence = Evidence(stdin=best_test.stdin, details={"session": best_test.id, "prompt_index": n, "expected_prompt": exp})
        if i >= len(prompts):
            if stopped_early:
                checks.append(_skipped(base(n, exp), policy, f"test:{best_test.id}", evidence,
                                       "Not checked: the program stopped before this input."))
                continue
            location = locate_text(exp, module)
            evidence.code = _line_excerpt(ctx, ex.file_path, location)
            checks.append(CheckResult(
                **base(n, exp), **policy.apply("fail", "major"), diagnosis="missing_prompt", location=location,
                message=f"The program never asked for input {n} ({exp!r}) in any session of the subject.",
                evidence=evidence,
            ))
            continue
        text, location = _prompt_text(prompts[i], exp)
        checks.append(_prompt_check(base(n, exp), policy, n, exp, text, location, evidence, ctx, ex.file_path))
    return checks


def _prompt_text(prompt: ActualPrompt, expected: str) -> tuple[str, Location | None]:
    """The text shown right before input n; a prompt printed on its own line (print + input()) counts."""
    newlines = expected.count("\n")
    text, location = prompt.tail(newlines)
    if text == "" and not expected.endswith("\n"):
        wider, wider_location = prompt.tail(newlines + 1)
        if wider.strip() and line_ratio(wider.rstrip("\n"), expected) >= PAIR_RATIO:
            return wider, wider_location
    return text, location


def _prompt_check(
    base: dict[str, Any], policy: _Policy, n: int, expected: str, actual: str, location: Location | None,
    evidence: Evidence, ctx: EvalContext, spec_path: str,
) -> CheckResult:
    evidence.details["actual_prompt"] = actual
    evidence.expected_value = ValueSnapshot(repr=repr(expected), type="str")
    evidence.actual_value = ValueSnapshot(repr=repr(actual), type="str")
    evidence.code = _line_excerpt(ctx, spec_path, location)
    where = f" (line {location.line} of {location.file})" if location and location.line else ""
    if actual == expected:
        return CheckResult(**base, **policy.apply("pass", None), location=location, evidence=evidence,
                           message=f"The input() prompt {n} matches the subject exactly{where}.")
    if actual == "":
        return CheckResult(**base, **policy.apply("fail", "major"), diagnosis="missing_prompt", location=location,
                           evidence=evidence,
                           message=f"Input {n} is read without the prompt {expected!r}{where}.")
    diff = diff_text(expected, actual)
    evidence.value_diff = diff
    severity: Severity = "minor" if only_minor(list(diff.kinds)) else "major"
    note = ""
    if actual.endswith("\n") and not expected.endswith("\n"):
        note = " The prompt is printed on its own line: pass it to input() instead of print()."
    return CheckResult(**base, **policy.apply("fail", severity), diagnosis="prompt_mismatch", location=location,
                       evidence=evidence,
                       message=f"The input() prompt {n} differs from the subject: {first_hint(diff)}{where}.{note}")


# ------------------------------------------------------------------------------------------------
# Import side effects
# ------------------------------------------------------------------------------------------------


def evaluate_import(exercise_id: str, res: JobResult, ctx: EvalContext) -> CheckResult | None:
    """Runtime check that importing a "functions" exercise module prints nothing, reads nothing, does not crash."""
    ex = ctx.spec.exercise(exercise_id)
    if ex is None or ex.kind != "functions":
        return None
    if res.status in ("harness_error", "syntax_error") or ctx.blocker(ex.file_path):
        return None   # reported by the structure/syntax checks
    policy = _Policy.of(ex, "runtime")
    stdout = res.import_stdout or res.stdout
    evidence = Evidence(actual_stdout=stdout or None)
    _run_evidence(res, evidence)
    evidence.actual_stdout = stdout or None
    base: dict[str, Any] = {"id": f"import_effects:{exercise_id}", "category": "runtime", "exercise_id": exercise_id,
                            "file": ex.file_path, "origin": ex.origin}
    problem = _import_problem(ex, res, stdout)
    if problem is None:
        return CheckResult(**base, **policy.apply("pass", None), title="No side effects at import", evidence=evidence,
                           message="Importing the module prints nothing, asks for no input and does not crash.")
    diagnosis, title, message, location = problem
    evidence.code = _line_excerpt(ctx, ex.file_path, location)
    return CheckResult(**base, **policy.apply("warning", "major"), title=title, message=message, diagnosis=diagnosis,
                       location=location, evidence=evidence)


_MAIN_GUARD = 'if __name__ == "__main__":'


def _import_problem(ex: ExerciseSpec, res: JobResult, stdout: str) -> tuple[str, str, str, Location | None] | None:
    exc = res.exception
    inputs = [e for e in res.events if e.kind == "input"]
    if inputs or (exc is not None and exc.type == "EOFError"):
        location = event_location(inputs[0]) if inputs else _exception_location(res)
        where = f" (line {location.line})" if location and location.line else ""
        return ("import_waits_input", "Waits for input when imported",
                f"Importing the module calls input(){where}: top-level code runs when the grader imports the file. "
                f"Move it under `{_MAIN_GUARD}`.", location)
    if res.status != "ok" or res.blocked_syscalls or (exc is not None and exc.type != "SystemExit"):
        failure = runtime_failure(res, context="import")
        if res.status == "ok" and exc is not None:
            text = f"Importing the module raised {exc.type}: {exc.message}."
        else:
            text = failure.message if failure else "Importing the module failed."
        return ("import_crash", "Crashes when imported", text, _exception_location(res))
    outputs = [e for e in res.events if e.kind == "output"]
    if (outputs or stdout) and not ex.import_side_effects_allowed:
        location = event_location(outputs[0]) if outputs else None
        shown = outputs[0].text if outputs else stdout
        where = f" (line {location.line})" if location and location.line else ""
        return ("import_side_effects", "Prints when imported",
                f"Importing the module prints {_preview(shown)}{where}: functions files must not execute code at import. "
                f"Remove the debug print or move it under `{_MAIN_GUARD}`.", location)
    return None
