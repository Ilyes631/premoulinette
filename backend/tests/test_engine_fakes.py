"""Fake collaborators for the pipeline unit tests (this module contains no tests).

Each fake mimics the documented contract of a module owned by another engineer, with just enough
behaviour to observe the orchestration: paths, blockers, stage order, persistence. Student code is
never executed: the fake sandbox answers from a table and records what it was given.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from premoulinette.engine.deps import EngineDeps
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo, SyntaxErrorInfo
from premoulinette.results.models import CheckResult, Location, SandboxInfo, ScoreSummary, TreeEntry
from premoulinette.runner.models import FunctionJob, ImportJob, JobResult, RunPlan, RunResults, ScriptJob
from premoulinette.spec.models import PracticalSpec
from test_api_fakes import FakeDockerStatus, fake_generate_tests, fake_list_tree, fake_read_git_info, fake_snapshot_from_path


# ---- static side ---------------------------------------------------------------------------------


def fake_detect_root(snapshot_root: Path, spec: PracticalSpec) -> SimpleNamespace:
    expected = spec.expected_files()
    matched = sum(1 for f in expected if (snapshot_root / f.path).exists())
    return SimpleNamespace(root="", strip_prefix="", matched=matched, expected=len(expected), note=None, confident=True)


def fake_analyze_project(root: Path, files: list[str]) -> dict[str, ModuleInfo]:
    out: dict[str, ModuleInfo] = {}
    for rel in files:
        source = (root / rel).read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            out[rel] = ModuleInfo(path=rel, ok=False, syntax_error=SyntaxErrorInfo(message=exc.msg, line=exc.lineno))
            continue
        functions = [
            FunctionInfo(name=n.name, line=n.lineno, end_line=n.end_lineno or n.lineno)
            for n in tree.body if isinstance(n, ast.FunctionDef)
        ]
        out[rel] = ModuleInfo(path=rel, ok=True, functions=functions, line_count=len(source.splitlines()))
    return out


def fake_check_structure(
    spec: PracticalSpec, snapshot_root: Path, det: Any, tree: list[TreeEntry]
) -> tuple[list[CheckResult], list[TreeEntry], dict[str, str | None]]:
    """Exact path, else same basename elsewhere (misplaced: file_map points to it), else missing."""
    files = [e.path for e in tree if e.kind == "file"]
    checks: list[CheckResult] = []
    file_map: dict[str, str | None] = {}
    for req in spec.expected_files():
        base = {"id": f"structure:file:{req.path}", "category": "structure", "file": req.path}
        if req.path in files:
            file_map[req.path] = req.path
            checks.append(CheckResult(**base, status="pass", title="Present", message="ok"))
            continue
        found = next((f for f in files if f.rsplit("/", 1)[-1] == req.path.rsplit("/", 1)[-1]), None)
        file_map[req.path] = found
        diagnosis = "misplaced_file" if found else "missing_file"
        checks.append(CheckResult(**base, status="fail", severity="critical", title=diagnosis, message=diagnosis,
                                  diagnosis=diagnosis))
    annotated = [e.model_copy(update={"status": "expected"}) for e in tree]
    return checks, annotated, file_map


def fake_check_syntax(modules: dict[str, ModuleInfo], file_map: dict[str, str | None], spec: PracticalSpec) -> list[CheckResult]:
    """Deliberately reports ``file`` as the *actual* path: the pipeline must normalize it."""
    checks = []
    for spec_path, actual in file_map.items():
        if actual is None or actual not in modules:
            continue
        mod = modules[actual]
        checks.append(CheckResult(
            id=f"syntax:{spec_path}", category="syntax", status="pass" if mod.ok else "fail",
            severity=None if mod.ok else "critical", title="Syntax", message="m", file=actual,
            location=Location(file=actual, line=mod.syntax_error.line if mod.syntax_error else None),
            diagnosis=None if mod.ok else "syntax_error",
        ))
    return checks


def fake_check_functions(spec: PracticalSpec, modules: dict[str, ModuleInfo], file_map: dict[str, str | None]) -> list[CheckResult]:
    checks = []
    for ex in spec.exercises:
        mod = modules.get(file_map.get(ex.file_path) or "")
        for fn in ex.functions:
            present = mod is not None and mod.function(fn.name) is not None
            checks.append(CheckResult(
                id=f"function:{ex.id}:{fn.name}", category="functions", status="pass" if present else "fail",
                severity=None if present else "critical", title=fn.name, message="m", file=ex.file_path,
                diagnosis=None if present else "missing_function",
            ))
    return checks


def no_checks(*_: Any, **__: Any) -> list[CheckResult]:
    return []


# ---- sandbox -------------------------------------------------------------------------------------


@dataclass
class FakeSandbox:
    """Answers from ``returns`` (job id -> return repr) and records every call."""

    mode: str = "local"
    returns: dict[str, str] = field(default_factory=dict)
    drop: set[str] = field(default_factory=set)        # job ids for which no result is returned
    error: Exception | None = None
    calls: list[tuple[RunPlan, Path]] = field(default_factory=list)
    seen_sources: dict[str, str] = field(default_factory=dict)

    def run(self, plan: RunPlan, project_root: Path) -> RunResults:
        self.calls.append((plan, project_root))
        if self.error is not None:
            raise self.error
        results = []
        for job in plan.jobs:
            if job.id in self.drop:
                continue
            path = job.script_path if isinstance(job, ScriptJob) else job.module_path
            self.seen_sources[job.id] = (project_root / path).read_text(encoding="utf-8")
            results.append(self._result(job))
        return RunResults(results=results, python_version="3.12.7", sandbox_mode=self.mode, errors=[])

    def _result(self, job: FunctionJob | ScriptJob | ImportJob) -> JobResult:
        if isinstance(job, FunctionJob):
            value = self.returns.get(job.id, "None")
            return JobResult(id=job.id, kind="function", status="ok", return_repr=value,
                             return_type=type(ast.literal_eval(value)).__name__, return_literal=True)
        if isinstance(job, ScriptJob):
            return JobResult(id=job.id, kind="script", status="ok", stdout="Hi Bob\n", exit_code=0)
        return JobResult(id=job.id, kind="import", status="ok", exit_code=0)

    def info(self) -> SandboxInfo:
        return SandboxInfo(mode=self.mode, warnings=["fake sandbox"])  # type: ignore[arg-type]


@dataclass
class SandboxFactory:
    sandbox: FakeSandbox
    requested: list[tuple[str, str]] = field(default_factory=list)

    def __call__(self, mode: str, *, image: str = "python:3.12-slim") -> FakeSandbox:
        self.requested.append((mode, image))
        self.sandbox.mode = mode
        return self.sandbox


# ---- evaluation ----------------------------------------------------------------------------------


def fake_eval_context(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _file_of(ctx: Any, exercise_id: str) -> str | None:
    ex = ctx.spec.exercise(exercise_id)
    return ex.file_path if ex else None


def fake_evaluate_function(gen: Any, res: JobResult | None, ctx: Any) -> CheckResult:
    spec_path = _file_of(ctx, gen.exercise_id)
    base = {"id": f"test:{gen.test.id}", "category": gen.category, "title": gen.test.call_repr(), "message": "m",
            "test_id": gen.test.id, "exercise_id": gen.exercise_id, "function": gen.test.function, "file": spec_path,
            "mandatory": gen.category != "heuristic_tests"}
    if res is None:
        return CheckResult(**base, status="skipped", blocked_by=ctx.blocked.get(spec_path or ""))
    ok = res.return_repr == gen.test.expected_return
    actual = ctx.file_map.get(spec_path) or spec_path
    return CheckResult(**base, status="pass" if ok else "fail", severity=None if ok else "major",
                       diagnosis=None if ok else "wrong_value", location=Location(file=actual, line=1))


def fake_evaluate_script(gen: Any, res: JobResult | None, ctx: Any) -> list[CheckResult]:
    spec_path = _file_of(ctx, gen.exercise_id)
    base = {"id": f"test:{gen.test.id}", "category": "output", "title": "Session", "message": "m",
            "test_id": gen.test.id, "exercise_id": gen.exercise_id, "file": spec_path}
    if res is None:
        return [CheckResult(**base, status="skipped", blocked_by=ctx.blocked.get(spec_path or ""))]
    ok = res.stdout == gen.test.expected_stdout
    return [CheckResult(**base, status="pass" if ok else "fail", severity=None if ok else "major")]


def fake_evaluate_import(exercise_id: str, res: JobResult, ctx: Any) -> CheckResult | None:
    return CheckResult(id=f"import_effects:{exercise_id}", category="runtime", status="pass", title="Import",
                       message="m", exercise_id=exercise_id, file=_file_of(ctx, exercise_id))


# ---- score -----------------------------------------------------------------------------------------


def fake_compute_score(checks: list[CheckResult], spec: PracticalSpec, *, spec_reviewed: bool, sandbox_mode: str) -> ScoreSummary:
    mandatory = [c for c in checks if c.mandatory and c.status in ("pass", "warning", "fail", "skipped")]
    passed = sum(1 for c in mandatory if c.status in ("pass", "warning"))
    failures = len(mandatory) - passed
    readiness = round(100 * passed / len(mandatory), 1) if mandatory else 0.0
    return ScoreSummary(
        readiness=readiness, mandatory_readiness=readiness, mandatory_passed=passed, mandatory_total=len(mandatory),
        mandatory_failures=failures, bonus_completion=None, bonus_passed=0, bonus_total=0,
        confidence="high" if sandbox_mode == "docker" else "medium",
        verdict="ready" if failures == 0 else "not_ready",
        verdict_title="READY TO SUBMIT" if failures == 0 else "DO NOT SUBMIT YET", verdict_message="m",
    )


# ---- assembly --------------------------------------------------------------------------------------


@dataclass
class FakeWorld:
    deps: EngineDeps
    sandbox: FakeSandbox
    factory: SandboxFactory
    fixes_calls: list[int] = field(default_factory=list)


def make_world(*, docker: FakeDockerStatus | None = None, fixes_error: Exception | None = None, **overrides: Any) -> FakeWorld:
    sandbox = FakeSandbox(returns={"is_safe#ex1": "True", "is_safe#ex2": "False", "is_safe#derived1": "True"})
    factory = SandboxFactory(sandbox)
    fixes_calls: list[int] = []

    def attach_fixes(checks: list[CheckResult], sources: dict[str, str], modules: dict[str, ModuleInfo]) -> None:
        fixes_calls.append(len(checks))
        if fixes_error is not None:
            raise fixes_error

    deps = replace(
        EngineDeps(),
        snapshot_from_path=fake_snapshot_from_path,
        detect_root=fake_detect_root,
        resolve=lambda spec_path, det: spec_path,
        list_tree=fake_list_tree,
        read_git_info=fake_read_git_info,
        analyze_project=fake_analyze_project,
        check_structure=fake_check_structure,
        check_git=no_checks,
        check_syntax=fake_check_syntax,
        check_functions=fake_check_functions,
        check_constraints=no_checks,
        check_import_side_effects=no_checks,
        generate_tests=fake_generate_tests,
        detect_docker=lambda image="python:3.12-slim", timeout=4.0: docker or FakeDockerStatus(image=image),
        get_sandbox=factory,
        eval_context=fake_eval_context,
        evaluate_function=fake_evaluate_function,
        evaluate_script=fake_evaluate_script,
        evaluate_import=fake_evaluate_import,
        attach_fixes=attach_fixes,
        compute_score=fake_compute_score,
    )
    if overrides:
        deps = replace(deps, **overrides)
    return FakeWorld(deps=deps, sandbox=sandbox, factory=factory, fixes_calls=fixes_calls)
