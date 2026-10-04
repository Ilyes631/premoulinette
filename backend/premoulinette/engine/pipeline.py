"""Analysis pipeline: subject spec + project snapshot -> persisted :class:`AnalysisReport`.

Order (ARCHITECTURE.md "Pipeline"): sandbox choice, snapshot refresh, root detection, tree,
structure, git, AST analysis, syntax/function/import-effect checks, test generation, one sandbox
run for every job, evaluation (explicit then derived/heuristic), constraints, fixes, score, report.

Path convention: ``file_map`` maps spec paths -> snapshot-relative paths; ``modules`` and
``sources`` are keyed by snapshot-relative paths (== ``Location.file``). Every ``CheckResult.file``
of the final report is a spec path when the file is an expected one (stable across analyses).

Any failure of a check producer aborts the analysis: silently dropping a family of checks could
turn a failing project into a "ready" verdict. Only fix suggestions are best-effort.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from premoulinette.config import SNAPSHOTS_KEPT_PER_PROJECT, ensure_dirs
from premoulinette.engine.deps import EngineDeps, default_deps
from premoulinette.engine.jobs import JobError
from premoulinette.engine.planning import PlannedRun, build_run_plan
from premoulinette.engine.sandbox_select import decide_sandbox
from premoulinette.engine.snapshots import (
    count_python_files,
    find_git_root,
    new_snapshot_dir,
    prefix_git_paths,
    prune_snapshots,
    relative_posix,
)
from premoulinette.results.models import (
    AnalysisReport,
    CheckResult,
    GitInfo,
    ProjectSummary,
    SubjectSummary,
    TreeEntry,
)
from premoulinette.runner.models import JobResult, RunPlan
from premoulinette.store.db import ProjectRecord, Settings, Store, SubjectRecord

log = logging.getLogger(__name__)

STAGES: list[tuple[str, str]] = [
    ("subject", "Parsing subject…"),
    ("repository", "Inspecting repository…"),
    ("compile", "Compiling Python files…"),
    ("explicit", "Running explicit tests…"),
    ("derived", "Running derived tests…"),
    ("constraints", "Checking constraints…"),
    ("report", "Building report…"),
]
_STAGE_START = {
    "subject": 0.0, "repository": 0.05, "compile": 0.25, "explicit": 0.40,
    "derived": 0.75, "constraints": 0.85, "report": 0.92,
}
_STATUS_RANK = {"pass": 0, "info": 1, "bonus": 2, "warning": 3, "skipped": 4, "fail": 5}

ProgressFn = Callable[[str, float], None]


class AnalysisError(JobError):
    """The analysis cannot be performed (shown verbatim to the user)."""


def run_analysis(
    subject: SubjectRecord,
    project: ProjectRecord,
    settings: Settings,
    store: Store,
    progress: ProgressFn,
    *,
    deps: EngineDeps | None = None,
    snapshots_dir: Path | None = None,
) -> AnalysisReport:
    """Run a full analysis, save it in ``store`` and return it.

    ``snapshots_dir`` is where path/demo projects are re-copied (default ``<DATA_DIR>/snapshots``).
    """
    run = _AnalysisRun(
        subject, project, settings, store, progress,
        deps or default_deps(), snapshots_dir or ensure_dirs().snapshots,
    )
    return run.execute()


@dataclass
class _Repo:
    root: Path
    project: ProjectRecord
    det: Any                              # RootDetection
    tree: list[TreeEntry]                 # raw tree (list_tree)
    annotated_tree: list[TreeEntry]       # tree annotated by check_structure
    file_map: dict[str, str | None]
    git: GitInfo


class _AnalysisRun:
    def __init__(
        self, subject: SubjectRecord, project: ProjectRecord, settings: Settings, store: Store,
        progress: ProgressFn, deps: EngineDeps, snapshots_dir: Path,
    ) -> None:
        self.subject = subject
        self.project = project
        self.settings = settings
        self.store = store
        self.progress = progress
        self.deps = deps
        self.snapshots_dir = snapshots_dir
        self.spec = subject.spec.model_copy(deep=True)
        self.checks: list[CheckResult] = []
        self.warnings: list[str] = []
        self.modules: dict[str, Any] = {}
        self.sources: dict[str, str] = {}
        self.python_version: str | None = None

    # ---- orchestration ------------------------------------------------------------------------
    def execute(self) -> AnalysisReport:
        started = time.perf_counter()
        self._stage("subject")
        sandbox = self._select_sandbox()

        self._stage("repository")
        repo = self._inspect_repository()

        self._stage("compile")
        self._static_analysis(repo)

        self._stage("explicit")
        fn_tests, script_tests = self.deps.generate_tests(self.spec)
        planned = build_run_plan(
            self.spec, fn_tests, script_tests, self.modules, repo.file_map,
            default_timeout_s=self.settings.default_timeout_s,
        )
        self.warnings.extend(planned.warnings)
        results = self._execute(sandbox, planned.plan, repo.root)
        ctx = self.deps.eval_context(
            spec=self.spec, modules=self.modules, file_map=dict(repo.file_map),
            blocked=dict(planned.blocked_files), sources=self.sources, results=results,
        )
        explicit = [g for g in fn_tests if g.category == "explicit_tests"]
        others = [g for g in fn_tests if g.category != "explicit_tests"]
        for gen in explicit:
            self.checks.append(self._eval_function(gen, results, planned, ctx))
        for gen in script_tests:
            self.checks.extend(self._eval_script(gen, results, planned, ctx))
        for job_id, exercise_id in planned.import_jobs.items():
            res = results.get(job_id)
            if res is not None:
                check = self.deps.evaluate_import(exercise_id, res, ctx)
                if check is not None:
                    self.checks.append(check)

        self._stage("derived")
        for gen in others:
            self.checks.append(self._eval_function(gen, results, planned, ctx))

        self._stage("constraints")
        self.checks.extend(self.deps.check_constraints(self.spec, self.modules, repo.file_map))

        self._stage("report")
        report = self._build_report(sandbox, repo, started)
        self.store.save_analysis(report)
        self.progress("report", 1.0)
        return report

    def _stage(self, key: str) -> None:
        self.progress(key, _STAGE_START[key])

    # ---- sandbox ------------------------------------------------------------------------------
    def _select_sandbox(self) -> Any:
        status = None
        if self.settings.sandbox_mode != "local":
            try:
                status = self.deps.detect_docker(self.settings.docker_image)
            except Exception as exc:  # noqa: BLE001 - treated as "Docker unavailable"
                log.warning("Docker detection failed: %s", exc)
        decision = decide_sandbox(self.settings, status)
        if decision.mode is None:
            raise AnalysisError(decision.reason)
        if decision.fallback:
            self.warnings.append(decision.reason)
        return self.deps.get_sandbox(decision.mode, image=self.settings.docker_image)

    def _execute(self, sandbox: Any, plan: RunPlan, root: Path) -> dict[str, JobResult]:
        if not plan.jobs:
            return {}
        try:
            run = sandbox.run(plan, root)
        except JobError:
            raise
        except Exception as exc:
            log.exception("Sandbox run failed")
            raise AnalysisError(f"The sandbox failed to run the tests: {exc}") from exc
        self.python_version = run.python_version
        self.warnings.extend(f"Sandbox: {e}" for e in run.errors)
        by_id = {r.id: r for r in run.results}
        missing = [j.id for j in plan.jobs if j.id not in by_id]
        if missing:
            shown = ", ".join(missing[:5]) + ("…" if len(missing) > 5 else "")
            self.warnings.append(f"The sandbox returned no result for {len(missing)} job(s): {shown}")
        return by_id

    # ---- repository ---------------------------------------------------------------------------
    def _inspect_repository(self) -> _Repo:
        root, file_count, refreshed = self._refresh_snapshot()
        det = self.deps.detect_root(root, self.spec)
        if not getattr(det, "confident", True):
            note = getattr(det, "note", None)
            self.warnings.append(
                f"Repository root detection is uncertain ({det.matched}/{det.expected} expected paths found)"
                + (f": {note}" if note else ".")
            )
        tree = list(self.deps.list_tree(root))
        project = self.project
        if refreshed:
            project = project.model_copy(update={
                "snapshot_path": str(root), "file_count": file_count, "python_files": count_python_files(tree),
            })
            self.store.save_project(project)
        checks, annotated, file_map = self.deps.check_structure(self.spec, root, det, tree)
        self.checks.extend(checks)
        file_map = dict(file_map)
        git = self._git_info(root, det, file_map)
        self.checks.extend(self.deps.check_git(self.spec, git, file_map))
        return _Repo(root, project, det, tree, list(annotated), file_map, git)

    def _refresh_snapshot(self) -> tuple[Path, int, bool]:
        """Re-copy path/demo projects so the analysis sees the latest edits; zip/upload reuse theirs."""
        p = self.project
        if p.source_kind in ("path", "demo") and p.source_path:
            src = Path(p.source_path)
            if src.is_dir():
                dest = new_snapshot_dir(self.snapshots_dir, p.id)
                snap = self.deps.snapshot_from_path(src, dest, kind=p.source_kind)
                self.warnings.extend(snap.warnings)
                if snap.skipped:
                    shown = ", ".join(snap.skipped[:5]) + ("…" if len(snap.skipped) > 5 else "")
                    self.warnings.append(f"{len(snap.skipped)} item(s) were not copied from the project: {shown}")
                prune_snapshots(
                    self.snapshots_dir, p.id, keep=SNAPSHOTS_KEPT_PER_PROJECT,
                    protect=[dest, Path(snap.root), Path(p.snapshot_path)],
                )
                return Path(snap.root), snap.file_count, True
            self.warnings.append(
                f"The source folder {src} is no longer available: the last snapshot was analyzed instead."
            )
        root = Path(p.snapshot_path)
        if not root.is_dir():
            raise AnalysisError("The project snapshot is missing. Import the project again.")
        return root, p.file_count, False

    def _git_info(self, root: Path, det: Any, file_map: Mapping[str, str | None]) -> GitInfo:
        git_root = find_git_root(root, preferred=getattr(det, "root", "") or "")
        if git_root is None:
            return GitInfo(is_repo=False)
        prefix = relative_posix(git_root, root)
        info = self.deps.read_git_info(git_root, self._git_required_paths(det, file_map, prefix))
        return prefix_git_paths(info, prefix)

    def _git_required_paths(self, det: Any, file_map: Mapping[str, str | None], prefix: str) -> list[str]:
        """Expected files as paths relative to the git root (for ``git check-ignore``)."""
        out: list[str] = []
        for req in self.spec.expected_files():
            actual = file_map.get(req.path)
            if actual is None:
                actual = self.deps.resolve(req.path, det)
            if prefix:
                if not actual.startswith(prefix + "/"):
                    continue
                actual = actual[len(prefix) + 1:]
            if actual and actual not in out:
                out.append(actual)
        return out

    # ---- static analysis ----------------------------------------------------------------------
    def _static_analysis(self, repo: _Repo) -> None:
        py_files = [e.path for e in repo.tree if e.kind == "file" and e.path.endswith(".py")]
        self.modules = dict(self.deps.analyze_project(repo.root, py_files))
        self.sources = _read_sources(repo.root, self.modules.keys())
        self.checks.extend(self.deps.check_syntax(self.modules, repo.file_map, self.spec))
        self.checks.extend(self.deps.check_functions(self.spec, self.modules, repo.file_map))
        self.checks.extend(self.deps.check_import_side_effects(self.spec, self.modules, repo.file_map))

    # ---- evaluation ---------------------------------------------------------------------------
    def _eval_function(self, gen: Any, results: Mapping[str, JobResult], planned: PlannedRun, ctx: Any) -> CheckResult:
        blocker = planned.blocked_tests.get(gen.test.id)
        check = self.deps.evaluate_function(gen, None if blocker else results.get(gen.test.id), ctx)
        if blocker and not check.blocked_by:
            check.blocked_by = blocker
        return check

    def _eval_script(
        self, gen: Any, results: Mapping[str, JobResult], planned: PlannedRun, ctx: Any
    ) -> list[CheckResult]:
        blocker = planned.blocked_tests.get(gen.test.id)
        checks = list(self.deps.evaluate_script(gen, None if blocker else results.get(gen.test.id), ctx))
        if blocker:
            for c in checks:
                if not c.blocked_by:
                    c.blocked_by = blocker
        return checks

    # ---- report -------------------------------------------------------------------------------
    def _build_report(self, sandbox: Any, repo: _Repo, started: float) -> AnalysisReport:
        checks = dedupe_checks(normalize_check_files(self.checks, repo.file_map))
        try:
            self.deps.attach_fixes(checks, self.sources, self.modules)
        except Exception as exc:  # noqa: BLE001 - fixes are suggestions only
            log.exception("attach_fixes failed")
            self.warnings.append(f"Fix suggestions could not be computed: {exc}")
        info = sandbox.info()
        if info.python_version is None and self.python_version:
            info = info.model_copy(update={"python_version": self.python_version})
        score = self.deps.compute_score(
            checks, self.spec, spec_reviewed=self.spec.metadata.reviewed_by_user, sandbox_mode=info.mode
        )
        project = repo.project
        return AnalysisReport(
            id=uuid.uuid4().hex,
            number=self.store.next_number(self.subject.id, project.id),
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            subject=SubjectSummary(
                id=self.subject.id, title=self.subject.title, source_name=self.subject.source_name,
                language=self.spec.language, parser=self.subject.parser,
            ),
            project=ProjectSummary(
                id=project.id, name=project.name, source_kind=project.source_kind, path=project.source_path,
                detected_root=getattr(repo.det, "root", None), root_note=getattr(repo.det, "note", None),
                file_count=project.file_count, python_files=project.python_files, git=repo.git,
            ),
            sandbox=info,
            spec=self.spec,
            checks=checks,
            tree=repo.annotated_tree,
            score=score,
            pipeline_warnings=list(dict.fromkeys(self.warnings)),
        )


# ---- helpers (module level: unit-tested directly) --------------------------------------------------


def normalize_check_files(checks: list[CheckResult], file_map: Mapping[str, str | None]) -> list[CheckResult]:
    """Rewrite ``check.file`` from an actual snapshot path to its spec path when it is an expected file."""
    inverse: dict[str, str] = {}
    for spec_path, actual in file_map.items():
        if actual is not None and actual != spec_path:
            inverse.setdefault(actual, spec_path)
    for c in checks:
        if c.file and c.file not in file_map and c.file in inverse:
            c.file = inverse[c.file]
    return checks


def dedupe_checks(checks: list[CheckResult]) -> list[CheckResult]:
    """Keep one check per id (ids are the history key): the worst status wins, later on ties."""
    index: dict[str, int] = {}
    out: list[CheckResult] = []
    for c in checks:
        i = index.get(c.id)
        if i is None:
            index[c.id] = len(out)
            out.append(c)
        elif _STATUS_RANK.get(c.status, 0) >= _STATUS_RANK.get(out[i].status, 0):
            log.debug("Duplicate check id %s: keeping the %s result", c.id, c.status)
            out[i] = c
    return out


def _read_sources(root: Path, rel_paths: Any) -> dict[str, str]:
    sources: dict[str, str] = {}
    for rel in rel_paths:
        try:
            sources[rel] = (root / rel).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
    return sources
