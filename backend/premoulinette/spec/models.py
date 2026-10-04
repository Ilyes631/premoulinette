"""PracticalSpec — the normalized, language-agnostic contract of a practical assignment (TP).

This is the heart of PréMoulinette. Every other module consumes it:

    raw subject -> document extraction -> semantic parsing -> PracticalSpec -> validation
                                                               |
                     static analysis / structure / test generation / runner / scoring

Design rules
------------
* Every requirement carries an :class:`Origin` (provenance + confidence + subject excerpt) so the UI
  can always say *why* something is checked and whether it is official.
* Values (arguments, expected returns) are stored as **Python literal source strings**
  (``"True"``, ``"'True'"``, ``"(1, 2)"``). This keeps ``True`` (bool) and ``"True"`` (str)
  distinct through JSON and lets the runner rebuild exact typed values with ``ast.literal_eval``.
* Behaviour rules use a *restricted expression language* (a safe subset of Python expressions over
  parameter names, see ``premoulinette.testgen.oracle``). They are never executed with ``eval``.
* Paths are POSIX, relative to the repository root (``MysteryInc/FirstLaunch/kelvin.py``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

# --------------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------------

Provenance = Literal[
    "explicit",      # literally present in the subject (example, signature, listed file...)
    "derived",       # deduced deterministically from an explicit rule (boundary of `x <= limit`)
    "heuristic",     # extra case proposed by the system (zero, negative...) — never official
    "ai_extracted",  # extracted by an LLM and NOT found verbatim in the subject — needs review
    "user",          # added or edited by the user in the spec editor
]


class SourceRef(BaseModel):
    """Where a requirement was found in the subject."""

    model_config = ConfigDict(extra="forbid")

    excerpt: str | None = Field(default=None, description="Short verbatim quote from the subject (<= 300 chars).")
    section: str | None = Field(default=None, description="Heading path, e.g. 'Exercise 2 > Safe speed'.")
    line: int | None = Field(default=None, description="1-based line in the extracted plain text of the subject.")


class Origin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provenance: Provenance = "explicit"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: SourceRef | None = None
    note: str | None = None


def explicit(excerpt: str | None = None, section: str | None = None, line: int | None = None) -> Origin:
    return Origin(provenance="explicit", confidence=1.0, source=SourceRef(excerpt=excerpt, section=section, line=line))


# --------------------------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------------------------

Construct = Literal[
    "for", "while", "loop",            # loop = for or while
    "comprehension",                    # list/set/dict comprehensions and generator expressions
    "lambda", "recursion", "try", "global", "class", "import",
    "with", "yield", "fstring", "walrus", "match",
]


class Constraints(BaseModel):
    """Static-analysis rules. ``None`` for an allow-list means "no allow-list" (everything allowed)."""

    model_config = ConfigDict(extra="forbid")

    allowed_builtins: list[str] | None = Field(
        default=None, description="If set, ONLY these builtins may be called (e.g. ['input','print','len'])."
    )
    forbidden_builtins: list[str] = Field(default_factory=list, description="e.g. ['abs','max','min','eval']")
    allowed_imports: list[str] | None = Field(default=None, description="If set, only these modules may be imported. [] = no import allowed.")
    forbidden_imports: list[str] = Field(default_factory=list)
    forbidden_methods: list[str] = Field(default_factory=list, description="Attribute calls, e.g. ['sort','join','split']")
    forbidden_constructs: list[Construct] = Field(default_factory=list)
    required_constructs: list[Construct] = Field(default_factory=list)
    origin: Origin = Field(default_factory=Origin)

    def merged_with(self, other: "Constraints | None") -> "Constraints":
        """Exercise-level constraints override/extend global ones (other = exercise level)."""
        if other is None:
            return self.model_copy(deep=True)
        return Constraints(
            allowed_builtins=other.allowed_builtins if other.allowed_builtins is not None else self.allowed_builtins,
            forbidden_builtins=sorted(set(self.forbidden_builtins) | set(other.forbidden_builtins)),
            allowed_imports=other.allowed_imports if other.allowed_imports is not None else self.allowed_imports,
            forbidden_imports=sorted(set(self.forbidden_imports) | set(other.forbidden_imports)),
            forbidden_methods=sorted(set(self.forbidden_methods) | set(other.forbidden_methods)),
            forbidden_constructs=sorted(set(self.forbidden_constructs) | set(other.forbidden_constructs)),
            required_constructs=sorted(set(self.required_constructs) | set(other.required_constructs)),
            origin=other.origin,
        )

    def is_empty(self) -> bool:
        return (
            self.allowed_builtins is None and not self.forbidden_builtins and self.allowed_imports is None
            and not self.forbidden_imports and not self.forbidden_methods and not self.forbidden_constructs
            and not self.required_constructs
        )


# --------------------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------------------


class Param(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    annotation: str | None = None   # source text, e.g. "int", "list[int]"
    default: str | None = None      # python literal source, e.g. "0", "None"


class FunctionSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    params: list[Param] = Field(default_factory=list)
    return_annotation: str | None = None

    def render(self) -> str:
        def p(x: Param) -> str:
            s = x.name
            if x.annotation:
                s += f": {x.annotation}"
            if x.default is not None:
                s += f" = {x.default}" if x.annotation else f"={x.default}"
            return s

        ret = f" -> {self.return_annotation}" if self.return_annotation else ""
        return f"def {self.name}({', '.join(p(x) for x in self.params)}){ret}"


class BehaviorRule(BaseModel):
    """One machine-checkable behaviour rule, evaluated by the safe oracle.

    ``when`` is a restricted boolean expression over parameter names (``"speed <= limit"``,
    ``"2 < vertical_speed <= 5"``). ``when=None`` means *otherwise* (default branch).
    Rules of a function are evaluated in order; the first matching rule gives the expected result.
    ``returns`` is a restricted expression (``"True"``, ``"'Crash!'"``, ``"celsius + 273.15"``,
    ``"f'Hello {name}'"``).
    """

    model_config = ConfigDict(extra="forbid")

    when: str | None = None
    returns: str | None = None
    raises: str | None = Field(default=None, description="Expected exception type name, e.g. 'ValueError'.")
    description: str | None = Field(default=None, description="Human wording from the subject.")
    origin: Origin = Field(default_factory=Origin)


CompareMode = Literal["auto", "exact", "float_tolerance"]


class FunctionTest(BaseModel):
    """A call ``function(*args, **kwargs)`` and its expected outcome."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, unique inside the spec, e.g. 'is_safe#ex1'.")
    function: str
    args: list[str] = Field(default_factory=list, description="Each positional arg as python literal source.")
    kwargs: dict[str, str] = Field(default_factory=dict)
    expected_return: str | None = Field(default=None, description="Python literal source. None = only check type/no crash.")
    expected_type: str | None = Field(default=None, description="Type name, e.g. 'bool'. Inferred from expected_return if None.")
    expected_stdout: str | None = Field(default=None, description="Exact stdout of the call. None = not checked.")
    expected_exception: str | None = None
    compare: CompareMode = "auto"
    timeout_s: float = Field(default=5.0, gt=0, le=60)
    origin: Origin = Field(default_factory=Origin)

    def call_repr(self) -> str:
        parts = list(self.args) + [f"{k}={v}" for k, v in self.kwargs.items()]
        return f"{self.function}({', '.join(parts)})"


class FunctionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signature: FunctionSignature
    description: str | None = None
    rules: list[BehaviorRule] = Field(default_factory=list)
    reference: str | None = Field(
        default=None, description="Restricted expression giving the expected return for any input, e.g. 'celsius + 273.15'."
    )
    must_return: bool = Field(default=True, description="The function must RETURN its result (not print it).")
    may_print: bool = Field(default=False, description="Printing inside the function is acceptable.")
    tests: list[FunctionTest] = Field(default_factory=list)
    origin: Origin = Field(default_factory=Origin)

    @property
    def name(self) -> str:
        return self.signature.name


# --------------------------------------------------------------------------------------------
# Scripts (interactive programs run with stdin)
# --------------------------------------------------------------------------------------------


class InteractionStep(BaseModel):
    """One step of an expected terminal session. ``output`` = what the program writes,
    ``input`` = one line typed by the user (without its trailing newline)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["output", "input"]
    text: str


def steps_to_io(steps: list[InteractionStep]) -> tuple[str, str]:
    """Return ``(stdin, expected_raw_stdout)`` for a transcript.

    When stdin is piped, typed input is NOT echoed in stdout, so the raw stdout is the
    concatenation of output steps only. Each input line is terminated by ``\\n`` in stdin.
    """
    stdin = "".join(s.text + "\n" for s in steps if s.kind == "input")
    stdout = "".join(s.text for s in steps if s.kind == "output")
    return stdin, stdout


class ScriptTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. 'launch_sequence#session1'.")
    title: str | None = None
    argv: list[str] = Field(default_factory=list)
    stdin: str = Field(default="", description="Full stdin; each typed line ends with \\n.")
    steps: list[InteractionStep] | None = Field(default=None, description="Expected session as shown in the subject.")
    expected_stdout: str | None = Field(default=None, description="Exact raw stdout (typed input NOT echoed).")
    expected_exit_code: int | None = 0
    match: Literal["exact", "contains"] = "exact"
    timeout_s: float = Field(default=5.0, gt=0, le=60)
    origin: Origin = Field(default_factory=Origin)

    @model_validator(mode="after")
    def _fill_from_steps(self) -> "ScriptTest":
        if self.steps:
            stdin, stdout = steps_to_io(self.steps)
            if not self.stdin:
                self.stdin = stdin
            if self.expected_stdout is None:
                self.expected_stdout = stdout
        return self


class ScriptSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompts: list[str] = Field(
        default_factory=list, description="Exact input() prompts expected, in order, e.g. ['Pilot name: ']."
    )
    required_outputs: list[str] = Field(default_factory=list, description="Exact lines/fragments that must appear in stdout.")
    tests: list[ScriptTest] = Field(default_factory=list)
    origin: Origin = Field(default_factory=Origin)


# --------------------------------------------------------------------------------------------
# Exercises / structure / spec
# --------------------------------------------------------------------------------------------

ExerciseKind = Literal["functions", "script", "file"]


class ExerciseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Slug, unique, e.g. 'safe_speed'.")
    title: str
    kind: ExerciseKind = "functions"
    required: bool = True
    bonus: bool = False
    file_path: str = Field(description="POSIX path relative to repo root.")
    description: str | None = None
    functions: list[FunctionSpec] = Field(default_factory=list)
    script: ScriptSpec | None = None
    constraints: Constraints | None = Field(default=None, description="Exercise-level constraints (merged over global).")
    import_side_effects_allowed: bool = Field(
        default=False, description="If False, importing the module must not print/ask input (functions exercises)."
    )
    origin: Origin = Field(default_factory=Origin)

    @model_validator(mode="after")
    def _bonus_not_required(self) -> "ExerciseSpec":
        if self.bonus:
            self.required = False
        return self


class FileRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: Literal["file", "directory"] = "file"
    required: bool = True
    bonus: bool = False
    description: str | None = None
    origin: Origin = Field(default_factory=Origin)


DEFAULT_FORBIDDEN_PATTERNS = [
    "__pycache__/", "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db", "*~", "*.swp", "*.swo", ".idea/",
    ".vscode/", ".ipynb_checkpoints/", "venv/", ".venv/", "*.egg-info/", "*.tmp", "*.bak", "*.orig",
]


class StructureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[FileRequirement] = Field(default_factory=list, description="Expected files/dirs (required, optional, bonus).")
    forbidden_patterns: list[str] = Field(
        default_factory=lambda: list(DEFAULT_FORBIDDEN_PATTERNS),
        description="Glob patterns of files that should NOT be submitted (trailing / = directory).",
    )
    forbidden_patterns_are_errors: bool = Field(
        default=False, description="True if the subject explicitly forbids them (FAIL), else WARNING."
    )
    allow_extra_files: bool = True
    require_gitignore: bool = False
    origin: Origin = Field(default_factory=Origin)


class SpecMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Untitled assignment"
    course: str | None = None
    school: str | None = None
    deadline: str | None = None
    source_name: str | None = Field(default=None, description="Original subject file name.")
    source_sha256: str | None = None
    parser: str = Field(default="heuristic", description="'heuristic', 'ai:<model>', 'heuristic+ai:<model>', 'manual'.")
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_by_user: bool = False


class PracticalSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    metadata: SpecMetadata = Field(default_factory=SpecMetadata)
    language: str = "python"
    language_version: str | None = None
    structure: StructureSpec = Field(default_factory=StructureSpec)
    global_constraints: Constraints = Field(default_factory=Constraints)
    exercises: list[ExerciseSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="Parser notes / things it could not formalize.")

    # ---- helpers -------------------------------------------------------------------------
    def exercise(self, exercise_id: str) -> ExerciseSpec | None:
        return next((e for e in self.exercises if e.id == exercise_id), None)

    def effective_constraints(self, ex: ExerciseSpec) -> Constraints:
        return self.global_constraints.merged_with(ex.constraints)

    def all_function_tests(self) -> list[tuple[ExerciseSpec, FunctionSpec, FunctionTest]]:
        return [(e, f, t) for e in self.exercises for f in e.functions for t in f.tests]

    def all_script_tests(self) -> list[tuple[ExerciseSpec, ScriptTest]]:
        return [(e, t) for e in self.exercises if e.script for t in e.script.tests]

    def expected_files(self) -> list[FileRequirement]:
        """Structure files + one entry per exercise file (deduplicated by path)."""
        seen: dict[str, FileRequirement] = {f.path: f for f in self.structure.files}
        for e in self.exercises:
            if e.file_path not in seen:
                seen[e.file_path] = FileRequirement(
                    path=e.file_path, required=e.required and not e.bonus, bonus=e.bonus, origin=e.origin
                )
        return list(seen.values())

    @model_validator(mode="after")
    def _check_unique_ids(self) -> "PracticalSpec":
        ids = [e.id for e in self.exercises]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"Duplicate exercise ids: {sorted(dup)}")
        test_ids: list[str] = [t.id for _, _, t in self.all_function_tests()] + [t.id for _, t in self.all_script_tests()]
        dup_t = {i for i in test_ids if test_ids.count(i) > 1}
        if dup_t:
            raise ValueError(f"Duplicate test ids: {sorted(dup_t)}")
        return self


class SpecStats(BaseModel):
    language: str
    required_files: int
    functions: int
    known_tests: int
    script_tests: int
    constraints: int
    exercises: int
    mandatory_exercises: int
    bonus_exercises: int


def spec_stats(spec: PracticalSpec) -> SpecStats:
    c = spec.global_constraints
    n_constraints = (
        len(c.forbidden_builtins) + (1 if c.allowed_builtins is not None else 0) + len(c.forbidden_imports)
        + (1 if c.allowed_imports is not None else 0) + len(c.forbidden_constructs) + len(c.required_constructs)
        + len(c.forbidden_methods)
    )
    for e in spec.exercises:
        if e.constraints:
            x = e.constraints
            n_constraints += (
                len(x.forbidden_builtins) + (1 if x.allowed_builtins is not None else 0) + len(x.forbidden_imports)
                + (1 if x.allowed_imports is not None else 0) + len(x.forbidden_constructs)
                + len(x.required_constructs) + len(x.forbidden_methods)
            )
    return SpecStats(
        language=spec.language,
        required_files=sum(1 for f in spec.expected_files() if f.required),
        functions=sum(len(e.functions) for e in spec.exercises),
        known_tests=len(spec.all_function_tests()) + len(spec.all_script_tests()),
        script_tests=len(spec.all_script_tests()),
        constraints=n_constraints,
        exercises=len(spec.exercises),
        mandatory_exercises=sum(1 for e in spec.exercises if e.required and not e.bonus),
        bonus_exercises=sum(1 for e in spec.exercises if e.bonus),
    )
