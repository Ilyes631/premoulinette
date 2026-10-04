"""Build the sandbox :class:`RunPlan` from generated tests, and record why some tests cannot run.

Paths: ``file_map`` maps *spec* paths to *snapshot-relative* paths (``None`` = missing). Jobs always
use snapshot-relative paths (the sandbox runs on the snapshot root); blockers reference stable
check ids built from spec paths.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from premoulinette.languages.python.static_models import ModuleInfo
from premoulinette.runner.models import FunctionJob, ImportJob, RunPlan, ScriptJob
from premoulinette.spec.models import ExerciseSpec, PracticalSpec

SPEC_DEFAULT_TIMEOUT_S = 5.0   # FunctionTest/ScriptTest default: defers to Settings.default_timeout_s
MAX_TIMEOUT_S = 60.0


@dataclass
class PlannedRun:
    plan: RunPlan
    blocked_files: dict[str, str]                       # spec path -> blocking check id (EvalContext.blocked)
    blocked_tests: dict[str, str]                       # test id -> blocking check id
    import_jobs: dict[str, str] = field(default_factory=dict)   # import job id -> exercise id
    warnings: list[str] = field(default_factory=list)


def effective_timeout(test_timeout: float, default_timeout: float) -> float:
    value = default_timeout if test_timeout == SPEC_DEFAULT_TIMEOUT_S else test_timeout
    return max(0.1, min(MAX_TIMEOUT_S, float(value)))


def file_blockers(
    spec: PracticalSpec, modules: Mapping[str, ModuleInfo], file_map: Mapping[str, str | None]
) -> dict[str, str]:
    """Exercise files whose code cannot run: missing file, or Python file that does not parse."""
    blocked: dict[str, str] = {}
    for ex in spec.exercises:
        path = ex.file_path
        if path in blocked:
            continue
        actual = file_map.get(path)
        if actual is None:
            blocked[path] = f"structure:file:{path}"
        elif path.endswith(".py"):
            mod = modules.get(actual)
            if mod is None or not mod.ok:
                blocked[path] = f"syntax:{path}"
    return blocked


def _primary_exercises(spec: PracticalSpec, blocked: Mapping[str, str]) -> dict[str, ExerciseSpec]:
    """One "functions" exercise per runnable file (a mandatory one is preferred over a bonus one)."""
    primary: dict[str, ExerciseSpec] = {}
    for ex in spec.exercises:
        if ex.kind != "functions" or ex.file_path in blocked:
            continue
        current = primary.get(ex.file_path)
        if current is None or (current.bonus and not ex.bonus):
            primary[ex.file_path] = ex
    return primary


def build_run_plan(
    spec: PracticalSpec,
    function_tests: Sequence[Any],
    script_tests: Sequence[Any],
    modules: Mapping[str, ModuleInfo],
    file_map: Mapping[str, str | None],
    *,
    default_timeout_s: float,
) -> PlannedRun:
    """``function_tests``/``script_tests`` are GeneratedFunctionTest/GeneratedScriptTest objects."""
    blocked_files = file_blockers(spec, modules, file_map)
    planned = PlannedRun(plan=RunPlan(), blocked_files=blocked_files, blocked_tests={})
    job_ids: set[str] = set()

    def add(job: FunctionJob | ScriptJob | ImportJob) -> bool:
        if job.id in job_ids:
            planned.warnings.append(f"Duplicate test id {job.id!r}: only the first occurrence was run.")
            return False
        job_ids.add(job.id)
        planned.plan.jobs.append(job)
        return True

    for path, ex in _primary_exercises(spec, blocked_files).items():
        job_id = f"import:{ex.id}"
        if add(ImportJob(id=job_id, module_path=file_map[path] or path,
                         timeout_s=effective_timeout(SPEC_DEFAULT_TIMEOUT_S, default_timeout_s))):
            planned.import_jobs[job_id] = ex.id

    for gen in function_tests:
        test = gen.test
        ex = spec.exercise(gen.exercise_id)
        if ex is None:
            planned.warnings.append(f"Test {test.id!r} references an unknown exercise {gen.exercise_id!r}.")
            continue
        blocker = blocked_files.get(ex.file_path)
        actual = file_map.get(ex.file_path)
        if blocker is None and actual is not None:
            mod = modules.get(actual)
            if mod is None or mod.function(test.function) is None:
                blocker = f"function:{ex.id}:{test.function}"
        if blocker is not None or actual is None:
            planned.blocked_tests[test.id] = blocker or f"structure:file:{ex.file_path}"
            continue
        add(FunctionJob(
            id=test.id, module_path=actual, function=test.function, args=list(test.args),
            kwargs=dict(test.kwargs), timeout_s=effective_timeout(test.timeout_s, default_timeout_s),
        ))

    for gen in script_tests:
        test = gen.test
        ex = spec.exercise(gen.exercise_id)
        if ex is None:
            planned.warnings.append(f"Test {test.id!r} references an unknown exercise {gen.exercise_id!r}.")
            continue
        actual = file_map.get(ex.file_path)
        blocker = blocked_files.get(ex.file_path)
        if blocker is not None or actual is None:
            planned.blocked_tests[test.id] = blocker or f"structure:file:{ex.file_path}"
            continue
        add(ScriptJob(
            id=test.id, script_path=actual, argv=list(test.argv), stdin=test.stdin,
            timeout_s=effective_timeout(test.timeout_s, default_timeout_s),
        ))

    return planned
