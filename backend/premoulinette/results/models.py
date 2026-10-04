"""Result model: what an analysis produces. Consumed by scoring, reporting, explanations and the web UI.

Every diagnostic is a :class:`CheckResult`. A check is *deterministic* (computed by code); the AI layer
only ever explains an existing CheckResult, it never creates or changes one.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from premoulinette.spec.models import Origin, PracticalSpec

Status = Literal["pass", "fail", "warning", "info", "bonus", "skipped"]
"""pass/fail/warning/info as usual; ``bonus`` = bonus item not implemented or failing (never blocks);
``skipped`` = could not run (blocked by another failure, see ``blocked_by``)."""

Severity = Literal["critical", "major", "minor", "style"]

Category = Literal[
    "structure",        # files, folders, names, parasites
    "syntax",           # compilation / parsing
    "functions",        # presence, names, signatures, return-vs-print (static)
    "explicit_tests",   # tests literally given in the subject
    "derived_tests",    # tests deduced from explicit rules
    "heuristic_tests",  # extra cases proposed by the system (warnings only)
    "output",           # script stdout / prompts matching
    "constraints",      # forbidden builtins, imports, constructs
    "runtime",          # import side effects, crashes outside a test, timeouts at import
    "git",              # tracking, dirty tree
]


class Location(BaseModel):
    file: str                      # project-relative POSIX path
    line: int | None = None        # 1-based
    end_line: int | None = None
    col: int | None = None         # 0-based column (as in ast)


class CodeExcerpt(BaseModel):
    file: str
    start_line: int                # first line number of `lines`
    lines: list[str]               # raw source lines (no trailing newline)
    highlight: list[int] = Field(default_factory=list)  # absolute line numbers to highlight


class ValueSnapshot(BaseModel):
    repr: str                      # python repr, e.g. "'True'"
    type: str                      # type name, e.g. "str"


class DiffSegment(BaseModel):
    op: Literal["equal", "insert", "delete", "replace"]
    expected: str = ""             # text on the expected side ("" for insert)
    actual: str = ""               # text on the actual side ("" for delete)


class DiffLine(BaseModel):
    op: Literal["equal", "changed", "missing", "extra"]
    expected_lineno: int | None = None
    actual_lineno: int | None = None
    expected: str | None = None    # line text WITHOUT its terminator
    actual: str | None = None
    expected_eol: str = ""         # "\n", "\r\n" or "" (no terminator)
    actual_eol: str = ""
    segments: list[DiffSegment] = Field(default_factory=list)   # char-level, only for op == "changed"
    hints: list[str] = Field(default_factory=list)              # e.g. ["missing trailing space", "typo: 'o'→'a'"]
    source: Location | None = None  # student source line that produced the actual text (if known)


DiffKind = Literal[
    "identical", "typo", "case", "whitespace", "trailing_whitespace", "missing_newline", "extra_newline",
    "crlf", "missing_lines", "extra_lines", "different",
]


class TextDiff(BaseModel):
    expected: str
    actual: str
    equal: bool
    lines: list[DiffLine] = Field(default_factory=list)
    kinds: list[DiffKind] = Field(default_factory=list)
    summary: str = ""              # e.g. "1 character differs on line 7 (typo)"
    first_difference: int | None = None  # char offset in expected where it first differs


class ExceptionInfo(BaseModel):
    type: str
    message: str
    traceback: str = ""            # filtered to student frames
    location: Location | None = None


class TranscriptEvent(BaseModel):
    kind: Literal["output", "input", "stderr"]
    text: str
    location: Location | None = None   # source line of the print()/input() that produced it


class Evidence(BaseModel):
    call: str | None = None                    # "is_safe(200, 250)"
    argv: list[str] | None = None
    stdin: str | None = None
    expected_value: ValueSnapshot | None = None
    actual_value: ValueSnapshot | None = None
    value_diff: TextDiff | None = None          # when both values are str: char diff of the strings
    stdout_diff: TextDiff | None = None
    expected_stdout: str | None = None
    actual_stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    exception: ExceptionInfo | None = None
    timed_out: bool = False
    duration_ms: float | None = None
    transcript: list[TranscriptEvent] | None = None
    expected_steps: list[dict[str, str]] | None = None   # InteractionStep dumps
    rule: str | None = None                     # human/expr rule from the subject this test comes from
    code: CodeExcerpt | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Fix(BaseModel):
    """A *minimal* suggested change. Never applied automatically."""
    summary: str
    file: str | None = None
    patch: str | None = None        # unified diff (--- a/x +++ b/x @@ ...), minimal hunk
    before: str | None = None       # single-line convenience: "return \"True\""
    after: str | None = None        # "return True"
    confidence: Literal["high", "medium", "low"] = "high"


class CheckResult(BaseModel):
    id: str                         # STABLE across analyses (used by history comparison)
    category: Category
    status: Status
    severity: Severity | None = None    # set for fail/warning
    title: str                      # short, e.g. "Wrong return type"
    message: str                    # one deterministic sentence
    diagnosis: str | None = None    # machine code for explanation templates, e.g. "str_instead_of_bool"
    exercise_id: str | None = None
    function: str | None = None
    test_id: str | None = None
    file: str | None = None
    location: Location | None = None
    origin: Origin = Field(default_factory=Origin)
    mandatory: bool = True          # counts in Mandatory readiness
    bonus: bool = False
    blocked_by: str | None = None   # id of the check that prevented this one from running
    evidence: Evidence | None = None
    fix: Fix | None = None
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------------------------
# Project / environment summaries
# ---------------------------------------------------------------------------------------------


class GitInfo(BaseModel):
    is_repo: bool = False
    branch: str | None = None
    head: str | None = None           # short sha
    last_commit_message: str | None = None
    last_commit_date: str | None = None
    dirty: bool = False
    modified: list[str] = Field(default_factory=list)
    untracked: list[str] = Field(default_factory=list)
    staged: list[str] = Field(default_factory=list)
    ignored_required: list[str] = Field(default_factory=list)   # required files matched by .gitignore
    remote_url: str | None = None
    tags: list[str] = Field(default_factory=list)              # e.g. existing submit-* tags (read only)
    error: str | None = None


class TreeEntry(BaseModel):
    path: str                         # POSIX relative to the project snapshot root
    kind: Literal["file", "directory"]
    size: int | None = None
    status: Literal["expected", "missing", "extra", "parasite", "misplaced", "ok"] = "ok"
    required: bool | None = None
    bonus: bool = False
    git: Literal["tracked", "untracked", "modified", "ignored"] | None = None
    note: str | None = None


class SandboxInfo(BaseModel):
    mode: Literal["docker", "local"]
    image: str | None = None
    python_version: str | None = None
    network: bool = False
    limits: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------------------------


class CategoryScore(BaseModel):
    key: str
    label: str
    passed: int
    total: int
    score: float | None             # 0..100, None if total == 0
    failed: int = 0
    warnings: int = 0


class ExerciseScore(BaseModel):
    exercise_id: str
    title: str
    file: str
    bonus: bool
    required: bool
    status: Literal["pass", "fail", "warning", "missing", "not_implemented", "partial"]
    passed: int
    total: int
    score: float | None
    issues: int


class FileScore(BaseModel):
    file: str
    exercise_ids: list[str] = Field(default_factory=list)
    present: bool = True
    passed: int = 0
    total: int = 0
    score: float | None = None
    issues: int = 0
    worst_severity: Severity | None = None


class ScoreSummary(BaseModel):
    readiness: float                  # headline = mandatory readiness (0..100)
    mandatory_readiness: float
    mandatory_passed: int
    mandatory_total: int
    mandatory_failures: int
    bonus_completion: float | None    # None if the subject has no bonus
    bonus_passed: int
    bonus_total: int
    confidence: Literal["high", "medium", "low"]
    confidence_reasons: list[str] = Field(default_factory=list)
    categories: list[CategoryScore] = Field(default_factory=list)
    exercises: list[ExerciseScore] = Field(default_factory=list)
    files: list[FileScore] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)      # by status, and "critical"/"major"/... by severity
    verdict: Literal["ready", "not_ready"]
    verdict_title: str                # "READY TO SUBMIT" / "DO NOT SUBMIT YET"
    verdict_message: str


class SubjectSummary(BaseModel):
    id: str
    title: str
    source_name: str | None = None
    language: str
    parser: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    source_kind: Literal["path", "zip", "upload", "demo"]
    path: str | None = None           # original local path (path/demo kind)
    detected_root: str | None = None  # sub-folder of the snapshot used as repo root ('' = top)
    root_note: str | None = None
    file_count: int = 0
    python_files: int = 0
    git: GitInfo | None = None


class AnalysisReport(BaseModel):
    id: str
    number: int = 0                   # 1, 2, 3... per (subject, project) pair
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0
    subject: SubjectSummary
    project: ProjectSummary
    sandbox: SandboxInfo
    spec: PracticalSpec               # spec snapshot actually used
    checks: list[CheckResult] = Field(default_factory=list)
    tree: list[TreeEntry] = Field(default_factory=list)
    score: ScoreSummary
    pipeline_warnings: list[str] = Field(default_factory=list)


class AnalysisListItem(BaseModel):
    id: str
    number: int
    created_at: datetime
    subject_id: str
    project_id: str
    subject_title: str
    project_name: str
    readiness: float
    mandatory_readiness: float
    bonus_completion: float | None
    verdict: Literal["ready", "not_ready"]
    mandatory_failures: int


class CheckChange(BaseModel):
    id: str
    title: str
    file: str | None = None
    before: Status | None
    after: Status | None


class AnalysisComparison(BaseModel):
    base_id: str
    head_id: str
    readiness_delta: float
    fixed: list[CheckChange] = Field(default_factory=list)          # fail/warning -> pass
    new_failures: list[CheckChange] = Field(default_factory=list)   # pass/absent -> fail
    still_failing: list[CheckChange] = Field(default_factory=list)
    new_checks: list[CheckChange] = Field(default_factory=list)
    removed_checks: list[CheckChange] = Field(default_factory=list)
