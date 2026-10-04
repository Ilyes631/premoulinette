# PréMoulinette — Architecture & module contracts

> Source of truth for every contributor (human or agent). If you implement a module, implement
> **exactly** the public functions listed for it here (names, parameters, return types). Shared models
> are already written and MUST NOT be changed without coordination:
>
> * `backend/premoulinette/spec/models.py` — `PracticalSpec` (the TP contract)
> * `backend/premoulinette/results/models.py` — `CheckResult`, `TextDiff`, `AnalysisReport`, scores…
> * `backend/premoulinette/runner/models.py` — `RunPlan`, `JobResult`, `RunResults` (sandbox protocol)
> * `backend/premoulinette/languages/python/static_models.py` — `ModuleInfo` (AST analysis)

## Priorities

1. Correctness 2. Security 3. Useful diagnostics 4. UX 5. Extensibility 6. Extra features.
20 very reliable checks > 100 approximate ones. Never present a heuristic as official.
The AI layer only *explains* deterministic results; it never decides pass/fail.

## Pipeline

```
subject file ──extract──▶ SubjectDocument ──heuristic parser (+ optional AI parser + grounding)──▶ PracticalSpec
                                                                                   │ (user can review/edit)
project (path | zip | folder upload) ──snapshot (copy, limits, sanitize .git)──▶ snapshot dir
                                                                                   ▼
engine.run_analysis:
  1 detect repo root            project.root_detect
  2 structure checks            languages.python.checks_structure   (exact-case paths, misplaced, parasites)
  3 syntax + AST                languages.python.static              (ast.parse only, never executes)
  4 function/constraint checks  languages.python.checks_static
  5 test generation             testgen.generate                     (explicit / derived / heuristic)
  6 sandbox execution           sandbox.{docker,local} + harness     (one fresh child per job)
  7 evaluation                  compare.evaluate                     (JobResult → CheckResult, diffs, source mapping)
  8 git checks                  project.git_info + checks_structure.check_git
  9 fixes                       explain.fixes.attach_fixes           (deterministic minimal patches)
 10 scoring                     scoring.score
 11 report + persistence        report.export, store.db
```

## Directory layout

```
backend/premoulinette/
  __init__.py  __main__.py  config.py
  spec/        models.py (shared)  validate.py
  results/     models.py (shared)
  runner/      models.py (shared)
  subject/     document.py extract.py transcript.py heuristic.py ai_parser.py grounding.py pipeline.py
  project/     ingest.py tree.py root_detect.py git_info.py
  languages/   base.py
    python/    static_models.py (shared) static.py checks_structure.py checks_static.py builtins_catalog.py
               harness/run_plan.py harness/child.py   (stdlib only!)
  sandbox/     base.py detect.py docker.py local.py winjob.py
  testgen/     oracle.py generate.py
  compare/     values.py text_diff.py source_map.py evaluate.py
  explain/     templates.py fixes.py ai.py
  scoring/     score.py
  report/      export.py
  store/       db.py
  engine/      pipeline.py jobs.py
  api/         app.py security.py routes_*.py
backend/tests/   pytest, fixtures/projects/<variant>/
frontend/        Vite + React + TS + Tailwind
demo/            subject_demo.html, projects/mysteryinc_buggy, projects/mysteryinc_fixed
```

All imports are absolute (`from premoulinette.spec.models import PracticalSpec`). Python ≥ 3.11 syntax,
runs on 3.14 locally. Every module ships its own `backend/tests/test_<module>.py`.
Run tests: `backend\.venv\Scripts\python.exe -m pytest backend/tests -q` (from repo root, with
`backend` on the path — `backend/tests/conftest.py` inserts it).

---

## Module contracts

### `subject/` — owner: SUBJECT agent

```python
# document.py
class Block(BaseModel):
    kind: Literal["heading", "paragraph", "code", "list_item", "table_row"]
    text: str                       # plain text; for code: exact content (no HTML entities)
    level: int | None = None        # heading level 1..6
    lang: str | None = None         # code: "python", "terminal", None
    inputs: list[tuple[int, int]] = []   # code: (start, end) char spans marked as user input (<kbd>, <b> inside <pre>)
    inline_code: list[str] = []     # paragraph/list_item: contents of inline <code>/`x` spans, in order
    section: str = ""               # heading path "Exercise 2 — Safe speed"
    line: int = 0                   # 1-based line in `SubjectDocument.text`
class SubjectDocument(BaseModel):
    source_name: str
    media_type: Literal["html", "markdown", "text", "pdf"]
    title: str | None
    text: str                       # full plain text (for display, grounding and AI)
    blocks: list[Block]
    sha256: str
    warnings: list[str] = []

# extract.py
def extract_document(data: bytes, filename: str) -> SubjectDocument   # html/htm, md/markdown, txt, pdf (pypdf)
# transcript.py
def split_transcript(code: str, inputs: list[tuple[int,int]] | None = None,
                     known_inputs: list[str] | None = None) -> tuple[list[str], list[InteractionStep], float]
    # returns (commands e.g. ["python3 launch_sequence.py"], steps, confidence 0..1)
    # strips shell prompt lines ("42sh$ ...", "$ ...", "> python ..."); a transcript may contain several runs
def split_sessions(code, inputs) -> list[tuple[str, list[InteractionStep], float]]   # (command, steps, confidence) per run
# heuristic.py
class ParseResult(BaseModel):
    spec: PracticalSpec
    warnings: list[str] = []
    stats: dict[str, int] = {}
def parse_heuristic(doc: SubjectDocument) -> ParseResult
# grounding.py
def ground_spec(spec: PracticalSpec, doc: SubjectDocument) -> PracticalSpec
    # any test/rule/file whose literal text can't be found in doc.text gets provenance "ai_extracted", confidence<=0.6
# ai_parser.py   (Claude API, opt-in only; never called without consent)
def parse_with_ai(doc: SubjectDocument, api_key: str, model: str = "claude-sonnet-5-5") -> ParseResult
# pipeline.py
def parse_subject(data: bytes, filename: str, *, use_ai: bool = False, api_key: str | None = None) -> tuple[SubjectDocument, ParseResult]
```

Heuristic parser requirements (must work on `demo/subject_demo.html`, and generically on similar subjects):
* title from `<title>`/first h1; exercises = h2/h3 sections containing a file path (`File: x.py` or inline code ending in `.py`);
  sections under a heading containing "Bonus"/"Optional"/"Facultatif" ⇒ `bonus=True`.
* signatures: every `def name(...) -> T:` line in code blocks of the section ⇒ `FunctionSpec` (several per block allowed).
* doctest examples `>>> f(args)` + next line value ⇒ explicit `FunctionTest` (`expected_return` = literal source, e.g. `'Hard landing'`).
  Also support `f(args) -> value`, `f(args) == value`, `f(args)  # value`.
* rules: list items / lines `<condition> → <literal>` or `-> <literal>` where condition parses as an expression over param
  names ⇒ `BehaviorRule(when=..., returns=...)`; `otherwise → x` / `else → x` ⇒ `when=None`.
  Phrases "Return `True` if `cond`, otherwise return `False`" ⇒ two rules. Inline code that parses as an expression over
  the params and directly follows "return"/"returns"/":" (e.g. ``celsius + 273.15``, f-strings) ⇒ `reference`.
* terminal blocks (lang terminal / lines starting with `$`/`42sh$`) ⇒ `ScriptTest`s (one per run, steps via
  `split_sessions`), exercise `kind="script"`; prompts in quotes in the text (`"Pilot name: "`, preserving trailing spaces) ⇒ `ScriptSpec.prompts`.
* structure: tree blocks (`├──`, `└──`, indented listing) ⇒ `StructureSpec.files` with full POSIX paths;
  files inside a folder said to be optional ("files in bonus/ are optional") ⇒ `required=False, bonus=True`.
  "must contain a .gitignore" ⇒ `require_gitignore=True` + a FileRequirement for `.gitignore`.
  Warnings forbidding `__pycache__`/`.pyc` ⇒ `forbidden_patterns_are_errors=True`.
* builtins: "Authorized builtins" list ⇒ `allowed_builtins`; "Forbidden builtins/functions" ⇒ `forbidden_builtins`
  (names without parentheses); "No import is allowed" ⇒ `allowed_imports=[]`.
* "must return ... must not print" ⇒ `must_return=True, may_print=False`; "must not execute any code when imported" ⇒
  `import_side_effects_allowed=False` for function exercises.
* Every item gets an `Origin(provenance="explicit", source=SourceRef(excerpt, section, line))`.
* Test ids: `"<function>#ex<n>"` for function examples, `"<exercise_id>#session<n>"` for script runs. Exercise id = file stem
  (dedupe with suffix when two exercises share a file, e.g. bonus `emoji_grade` in `grade_landing.py` ⇒ id `emoji_grade`
  — when a section defines exactly one function, prefer the function name as id if the file stem is already taken).

**Golden expectation for the demo subject** (assert it in tests): title "TP 1 — MysteryInc: First Launch";
11 exercises: kelvin, safe_speed, grade_landing, fuel_share (2 functions), mission_clock, FIXME2 (average_speed),
access_code (script, 2 sessions), launch_sequence (script, 3 sessions), emoji_grade (bonus, file grade_landing.py),
max_altitude (bonus), countdown (bonus script, 1 session); 8 mandatory / 3 bonus;
allowed_builtins = [input, print, len, int, str, float, bool]; forbidden_builtins = [abs, max, min, round, sorted, sum, eval];
allowed_imports = []; `.gitignore` required; landing_grade has 3 rules; is_safe has 2 rules
(`speed <= limit` → `True`, otherwise → `False`); to_kelvin reference `celsius + 273.15`;
launch_sequence prompts = ["Pilot name: ", "Starting fuel: ", "Your choice: ", "Set a trap or collect evidence? (trap/evidence) "];
session 1 stdin = "Camille\n400\n2\ntrap\n" and expected_stdout begins with "Pilot name: Starting fuel: Where's the Mystery Machine headed today?\n".

### `project/` + `languages/python/` (static side) — owner: STATIC agent

```python
# project/ingest.py
class Snapshot(BaseModel):
    root: Path                 # absolute path of the snapshot copy (always a fresh copy, never the user's folder)
    source_kind: Literal["path", "zip", "upload", "demo"]
    source_path: str | None
    name: str
    file_count: int
    total_bytes: int
    skipped: list[str]         # skipped heavy dirs / too big files
    warnings: list[str]
LIMITS: max 5000 files, 50 MB total, 5 MB per file; skip dirs: node_modules, .venv, venv, env, .tox, .mypy_cache, .pytest_cache (keep __pycache__ — it's a diagnostic!)
def snapshot_from_path(src: Path, dest: Path, *, kind="path") -> Snapshot
def snapshot_from_zip(data: bytes, dest: Path, name: str) -> Snapshot       # zip-slip safe, no symlinks, bomb limits; strips a single top folder? NO — keep as is (root detection handles it)
def snapshot_from_upload(files: list[tuple[str, bytes]], dest: Path, name: str) -> Snapshot   # relpaths from webkitdirectory
def sanitize_git_dir(root: Path) -> None   # rewrite .git/config to a minimal safe config (keep [core] repositoryformatversion/bare=false + remote urls), delete .git/hooks/*
# project/tree.py
def list_tree(root: Path) -> list[TreeEntry]          # POSIX relative paths, sorted, dirs + files (skip .git internals)
# project/root_detect.py
class RootDetection(BaseModel): root: str ("" = snapshot top, else POSIX subpath); strip_prefix: str (spec path prefix to strip, "" if none); matched: int; expected: int; note: str | None; confident: bool
def detect_root(snapshot_root: Path, spec: PracticalSpec) -> RootDetection
    # tries every dir up to depth 3 as root, and stripping leading components of spec paths; picks max exact-case matches.
    # If a .git dir exists, the git root wins unless it matches nothing.
def resolve(spec_path: str, det: RootDetection) -> str   # spec path -> snapshot-relative path
# project/git_info.py
def read_git_info(repo_root: Path, required_paths: list[str]) -> GitInfo
    # git -c core.fsmonitor=false -c core.hooksPath=<empty dir> -c protocol.allow=never ..., env GIT_CONFIG_NOSYSTEM=1, GIT_TERMINAL_PROMPT=0, timeout 10s
    # branch, head, last commit, porcelain status (modified/untracked/staged), check-ignore of required paths, tags (read only)
    # NEVER writes: no fetch/push/tag/commit.

# languages/python/builtins_catalog.py
PYTHON_BUILTINS: frozenset[str]           # dir(builtins) callables, stable list (not dependent on host version quirks)
# languages/python/static.py
def analyze_source(source: str, rel_path: str) -> ModuleInfo       # ast only; never exec
def analyze_file(path: Path, rel_path: str) -> ModuleInfo          # utf-8 (utf-8-sig ok); encoding errors -> ok=False
def analyze_project(root: Path, files: list[str]) -> dict[str, ModuleInfo]   # rel POSIX path -> info, for every .py
# languages/python/checks_structure.py
def check_structure(spec, snapshot_root: Path, det: RootDetection, tree: list[TreeEntry]) -> tuple[list[CheckResult], list[TreeEntry], dict[str, str | None]]
    # returns (checks, annotated tree, file_map spec_path -> actual snapshot-relative path or None if missing)
    # exact-case existence (os.listdir comparison — Windows is case-insensitive!), misplaced files (same basename elsewhere,
    # or case-only mismatch) -> file_map points to the found file so tests can still run, + critical structure FAIL;
    # missing required -> critical FAIL; missing bonus file -> status "bonus"; parasites (forbidden_patterns) -> FAIL major
    # if forbidden_patterns_are_errors else WARNING minor; .gitignore; extra unexpected .py -> INFO.
def check_git(spec, git: GitInfo, file_map) -> list[CheckResult]
    # required file untracked -> FAIL major (category git) "not tracked: it will not be submitted";
    # required file ignored by .gitignore -> FAIL critical; dirty tree -> WARNING minor; parasites tracked -> listed.
# languages/python/checks_static.py
def check_syntax(modules: dict[str, ModuleInfo], file_map, spec) -> list[CheckResult]       # one check per expected .py (+ other .py as info)
def check_functions(spec, modules, file_map) -> list[CheckResult]
    # presence (critical), near-miss names via difflib (diagnosis "wrong_function_name", message names the found def),
    # function defined in another file (misplaced), param count (critical), param names (minor), annotations (style/info),
    # return-vs-print static hint (major, diagnosis "prints_instead_of_returns" when no value return and has print),
    # returns of constant str "True"/"False" in a -> bool function (diagnosis "str_instead_of_bool", static, major).
def check_constraints(spec, modules, file_map) -> list[CheckResult]
    # forbidden builtins (critical, one check per (file, builtin), location = first use, evidence lists all lines),
    # builtins outside allow-list (critical), referenced-only forbidden builtins (f = abs) and bypasses (__builtins__, getattr on builtins,
    # __import__, eval/exec) -> critical, forbidden imports / imports when allowed_imports == [] (critical),
    # forbidden methods, forbidden/required constructs. Bonus exercises -> status "bonus" instead of "fail".
    # A local def that shadows a builtin name is NOT a builtin call.
def check_import_side_effects(spec, modules, file_map) -> list[CheckResult]
    # static: top-level print/input/calls outside main guard in "functions" exercises -> WARNING major (diagnosis "import_side_effects")
```

Stable check ids (MUST follow): `structure:file:<spec_path>`, `structure:parasite:<path>`, `structure:gitignore`,
`structure:extra:<path>`, `syntax:<spec_path>`, `function:<exercise_id>:<fn>`, `signature:<exercise_id>:<fn>`,
`returns:<exercise_id>:<fn>`, `constraint:<exercise_id>:<rule>:<name>` (rule ∈ forbidden_builtin, builtin_not_allowed,
import, method, construct, required_construct), `import_effects:<exercise_id>`, `git:untracked:<path>`, `git:ignored:<path>`,
`git:dirty`, `test:<test_id>`, `prompt:<exercise_id>:<n>`.

### `sandbox/` + harness — owner: SANDBOX agent

```python
# sandbox/base.py
class Sandbox(Protocol):
    mode: Literal["docker", "local"]
    def run(self, plan: RunPlan, project_root: Path) -> RunResults: ...
    def info(self) -> SandboxInfo: ...
def get_sandbox(mode: Literal["docker", "local"], *, image: str = "python:3.12-slim") -> Sandbox
# sandbox/detect.py
class DockerStatus(BaseModel): available: bool; version: str | None; image: str; image_ready: bool; error: str | None
def detect_docker(image: str = "python:3.12-slim", timeout: float = 4.0) -> DockerStatus     # cached 30 s
def pull_image(image: str) -> tuple[bool, str]
```
* Harness (`languages/python/harness/run_plan.py`, `child.py`): stdlib only. `run_plan.py <plan.json>` reads the plan,
  runs each job in a fresh `python -X utf8 -E -s child.py` process (bounded parallelism), per-job timeout with process-tree
  kill, output caps, and prints `RunResults` JSON between `@@PREMOULINETTE_RESULTS_BEGIN@@` / `@@..._END@@` markers.
* `child.py`: installs an audit hook blocking network (`socket.connect`, `socket.bind`...), process creation
  (`subprocess.Popen`, `os.system`, `os.exec*`, `os.spawn*`, `os.fork`), and writes outside the sandbox temp dir;
  records blocked events in `blocked_syscalls` and raises PermissionError. Instruments `builtins.print` and `builtins.input`
  to record `RawEvent`s with the student file/line (via frame inspection) while producing **byte-identical** stdout
  (prompts written to stdout by `input`, no echo of typed text, `EOFError` when stdin is exhausted).
  Function jobs: import module from file path (module dir on sys.path so sibling imports work), capture import stdout,
  call with `ast.literal_eval`'d args, return `repr` + `type(x).__name__` + `return_literal`. Script jobs: `runpy.run_path(path, run_name="__main__")`,
  cwd = script dir, exit code semantics like `python file.py` (uncaught exception → traceback on stderr filtered to student frames, exit 1; SystemExit honored).
  Exceptions carry the last student frame file/line.
* Docker sandbox: `docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m,exec --memory 256m --memory-swap 256m
  --cpus 1 --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges --user 65534:65534
  -v <snapshot>:/work:ro -v <harness>:/harness:ro -v <plan dir>:/plan:ro -w /work <image> python /harness/run_plan.py /plan/plan.json`,
  global timeout (sum of job timeouts / parallel + 20 s) then `docker kill`.
* Local sandbox ("Developer mode"): copies the snapshot to a temp dir, minimal env (no secrets: drop everything except
  SYSTEMROOT, PATH (python dir only), TEMP/TMP → temp dir, PYTHONIOENCODING=utf-8, PYTHONUTF8=1), Windows Job Object
  (`winjob.py`, ctypes: kill-on-close, active process limit, job memory limit) or POSIX `resource` rlimits + new session;
  hard timeout with tree kill; temp dir always removed. `SandboxInfo.warnings` explains the weaker isolation.

### `testgen/` + `compare/` — owner: EVAL agent

```python
# testgen/oracle.py   (restricted evaluator — NEVER eval/exec)
class OracleError(Exception)
def parse_expr(src: str) -> ast.expr                         # raises OracleError if not in the safe subset
def safe_eval(src: str, env: dict[str, object]) -> object    # Constant, Name(env/True/False/None), BinOp, UnaryOp, BoolOp, Compare,
    # IfExp, Tuple/List/Dict/Set, Subscript, Slice, JoinedStr/FormattedValue (with format_spec), calls to SAFE_FUNCS
    # {abs,min,max,round,len,int,float,str,bool,sum,sorted}; guards: pow exponent <= 1000, sequences/strings <= 10_000 items, depth <= 50
def literal(src: str) -> object                              # ast.literal_eval wrapper with OracleError
def expected_for(fn: FunctionSpec, args: list[object]) -> tuple[bool, object | None, str | None]
    # (known, value, rule_text) from rules (first match, `when=None` = otherwise) then reference
def boundary_values(fn: FunctionSpec) -> list[dict[str, object]]   # param assignments around comparisons in rules
# testgen/generate.py
class GeneratedFunctionTest(BaseModel): test: FunctionTest; exercise_id: str; category: Literal["explicit_tests","derived_tests","heuristic_tests"]; rule: str | None
class GeneratedScriptTest(BaseModel): test: ScriptTest; exercise_id: str; category: Literal["explicit_tests","output"]
def generate_tests(spec: PracticalSpec) -> tuple[list[GeneratedFunctionTest], list[GeneratedScriptTest]]
    # explicit = spec tests (expected filled by oracle only if missing); derived = boundary cases from rules not already covered
    #   (provenance "derived", confidence 0.9, id "<fn>#derived<n>"); heuristic = 0/-1/large/""-style cases (<= 3 per function,
    #   provenance "heuristic", confidence 0.5, id "<fn>#heur<n>"): expected from oracle if known, else type-only check.
    # Script tests with expected_stdout -> category "output".

# compare/text_diff.py
def diff_text(expected: str, actual: str) -> TextDiff   # line alignment (difflib) + char segments + kinds + hints + summary
def visible(s: str) -> str                              # ' '→'·', '\t'→'→', '\n'→'↵\n', '\r'→'␍'
# compare/values.py
class ValueVerdict(BaseModel): ok: bool; kind: str; severity: Severity | None; title: str; message: str; diagnosis: str | None
def compare_values(expected_src: str | None, expected_type: str | None, res: JobResult, *, compare: CompareMode, annotation: str | None) -> ValueVerdict
    # kinds: equal, float_close (pass), type_mismatch_str_vs_bool ("str_instead_of_bool"), str_vs_number, int_vs_float (warning),
    # none_returned ("returns_none"; "prints_instead_of_returns" when the call stdout contains the expected value),
    # wrong_value, wrong_string (with value_diff), exception, timeout, import_error...
# compare/source_map.py
def locate_text(text: str, module: ModuleInfo | None) -> Location | None   # string literal that produced/contains a text fragment
# compare/evaluate.py
def evaluate_function(gen: GeneratedFunctionTest, res: JobResult | None, ctx: EvalContext) -> CheckResult
def evaluate_script(gen: GeneratedScriptTest, res: JobResult | None, ctx: EvalContext) -> list[CheckResult]
    # one CheckResult "test:<id>" for the whole stdout (exact compare, TextDiff with per-line `source` from events) +
    # prompt checks "prompt:<exercise_id>:<n>" comparing ScriptSpec.prompts with actual input() prompt events (once per exercise, from the first session that reaches them)
def evaluate_import(exercise_id: str, res: JobResult, ctx: EvalContext) -> CheckResult | None   # runtime import side effects / crash at import
class EvalContext(BaseModel): spec; modules: dict[str, ModuleInfo]; file_map: dict[str, str | None]; blocked: dict[str, str] (spec_path -> blocking check id); sources: dict[str, str]
```
Severity policy for tests: explicit/derived failing ⇒ `status="fail"` (`mandatory = not bonus`), severity: crash/timeout/missing
⇒ critical, wrong type/value ⇒ major, string differing only by typo/case/whitespace ⇒ minor (still FAIL!).
Heuristic failing ⇒ `status="warning"`, `mandatory=False`. Bonus exercise failing ⇒ `status="bonus"`, `mandatory=False`, `bonus=True`.
Tests that cannot run (file missing, syntax error, function missing) ⇒ `status="skipped"` + `blocked_by`, still mandatory (count as not passed).

### `explain/` — owner: EXPLAIN agent

```python
# fixes.py
def attach_fixes(checks: list[CheckResult], sources: dict[str, str], modules: dict[str, ModuleInfo]) -> None   # sets check.fix when deterministic
def build_fix(check: CheckResult, sources, modules) -> Fix | None
    # str_instead_of_bool: `- return "True"` `+ return True` (exact lines found via ModuleInfo.returns); typo/whitespace in a printed or
    # prompted string: replace the literal on the located line; wrong_function_name: rename def; missing trailing space;
    # prints_instead_of_returns; misplaced file: "move a -> b" (git mv); forbidden builtin: no patch, hint only (confidence low).
    # Patch = minimal unified diff hunk (1 line context). Never full-file rewrites.
# templates.py   (offline, deterministic, FR + EN, beginner-friendly)
class Explanation(BaseModel): title: str; markdown: str; provider: Literal["template","ai"]; language: Literal["fr","en"]; sent_payload: dict | None = None
def explain(check: CheckResult, lang: Literal["fr","en"] = "fr") -> Explanation           # keyed by check.diagnosis, generic fallback by category
def how_to_fix(check: CheckResult, lang="fr") -> Explanation                                # uses check.fix
def expected_behavior(check: CheckResult, spec: PracticalSpec, lang="fr") -> Explanation   # what the subject requires (rule, examples, session)
# ai.py   (opt-in, minimal payload, Anthropic Messages API)
def build_payload(check: CheckResult, mode: Literal["explain","fix"], lang) -> dict   # ONLY: rule, relevant code excerpt (<= 25 lines), expected, actual, deterministic diagnosis
def explain_with_ai(check, mode, lang, api_key, model="claude-sonnet-5-5") -> Explanation   # falls back to template on any error
```

### `scoring/`, `report/`, `store/` — owner: REPORT agent

```python
# scoring/score.py
def compute_score(checks: list[CheckResult], spec: PracticalSpec, *, spec_reviewed: bool, sandbox_mode: str) -> ScoreSummary
    # mandatory_readiness = 100 * passed / total over checks with mandatory=True and status in (pass, fail, skipped) [warnings/info excluded];
    # categories: Structure, Compilation, Required functions, Known tests (explicit), Derived tests, Output matching, Constraints, Git
    # bonus_completion = % of bonus exercises fully passing (None if no bonus); confidence high/medium/low with reasons
    # (AI-extracted unreviewed items, few tests per function, heuristic warnings, local sandbox, parse warnings).
    # verdict "ready" iff mandatory_failures == 0 (fail or skipped mandatory). Titles: "READY TO SUBMIT" / "DO NOT SUBMIT YET".
    # Message for ready: "All requirements that could be verified from the subject passed. Hidden grader tests may still exist."
    # exercises/files breakdown. Never claims an official grade.
# report/export.py
def to_json(report: AnalysisReport) -> str
def to_markdown(report: AnalysisReport) -> str      # sections: Repository, Subject, Mandatory requirements, Optional requirements, Structure,
    # Functions, Scripts, Constraints, Static analysis, Runtime analysis, Known tests, Derived tests, Warnings, Bonus
def to_html(report: AnalysisReport) -> str          # standalone, styled, printable, invisible chars visible in diffs
# store/db.py   (sqlite3 stdlib, file DATA_DIR/premoulinette.db, thread-safe connection per call)
class Store: __init__(db_path: Path)
  subjects: save_subject(rec) / get_subject(id) / list_subjects() / update_spec(id, spec) ;
  projects: save_project(rec) / get_project(id) / list_projects() ;
  analyses: save_analysis(report) / get_analysis(id) / list_analyses(subject_id=None, project_id=None, limit=50) -> list[AnalysisListItem] /
            next_number(subject_id, project_id) / compare(base_id, head_id) -> AnalysisComparison ;
  settings: get_settings() -> Settings / save_settings(Settings)
class SubjectRecord(BaseModel): id; title; source_name; created_at; updated_at; spec: PracticalSpec; document_text: str; document_html: str | None;
                                 media_type; parse_warnings: list[str]; parser: str; raw_path: str | None
class ProjectRecord(BaseModel): id; name; source_kind; source_path: str | None; created_at; snapshot_path: str; file_count; python_files
class Settings(BaseModel): sandbox_mode: Literal["auto","docker","local"]="auto"; local_mode_acknowledged: bool=False; docker_image="python:3.12-slim";
    ai_enabled: bool=False; ai_model="claude-sonnet-5-5"; ai_consent_subject: bool=False; ai_consent_code: bool=False;
    anthropic_api_key: str | None=None (never returned by the API, only `has_api_key`); explanation_language: Literal["fr","en"]="fr"; default_timeout_s: float=5.0
```

### `engine/` + `api/` — owner: API agent

```python
# engine/pipeline.py
STAGES = [("subject","Parsing subject…"),("repository","Inspecting repository…"),("compile","Compiling Python files…"),
          ("explicit","Running explicit tests…"),("derived","Running derived tests…"),("constraints","Checking constraints…"),("report","Building report…")]
def run_analysis(subject: SubjectRecord, project: ProjectRecord, settings: Settings, store: Store, progress: Callable[[str, float], None]) -> AnalysisReport
# engine/jobs.py — in-memory job manager (ThreadPoolExecutor(2)): JobState {id, kind, status queued|running|done|error, stage, stages[{key,label,status}], progress, result_id, error}
```
REST API (all under `/api`, JSON; mutating requests require header `X-PreMoulinette: 1`; Host must be localhost/127.0.0.1;
CORS only for http://localhost:5173 and http://127.0.0.1:5173):
```
GET  /api/health                         -> {ok, version, python, docker: DockerStatus, sandbox_mode_effective, ai: {configured, enabled}}
GET  /api/settings | PUT /api/settings   -> Settings (api key redacted -> has_api_key)
POST /api/sandbox/prepare                -> {job_id}           (docker pull)
POST /api/subjects   (multipart file)    -> SubjectView
POST /api/subjects/{id}/reparse {use_ai} -> SubjectView
GET  /api/subjects | /api/subjects/{id}  -> SubjectView {id,title,source_name,created_at,updated_at,parser,media_type,spec,stats: SpecStats,warnings,validation: [SpecIssue]}
PUT  /api/subjects/{id}/spec  (PracticalSpec JSON) -> SubjectView | 422 {detail: [{loc,msg}]}
GET  /api/subjects/{id}/tests            -> {explicit:[...], derived:[...], heuristic:[...], scripts:[...]} (GeneratedFunctionTest / GeneratedScriptTest)
GET  /api/subjects/{id}/document         -> {text, html | null, media_type}
GET  /api/spec/schema                    -> PracticalSpec JSON schema
POST /api/projects  (multipart: file=zip | files[]+paths[] | form field path) -> ProjectView {id,name,source_kind,source_path,file_count,python_files,tree,git,language:"python"}
GET  /api/projects/{id} ; GET /api/projects/{id}/file?path=...  -> {path, content, language}
POST /api/analyses {subject_id, project_id} -> {job_id}
GET  /api/jobs/{id}                      -> JobState
GET  /api/analyses?subject_id=&project_id=&limit= -> [AnalysisListItem]
GET  /api/analyses/{id}                  -> AnalysisReport
GET  /api/analyses/{id}/compare/{base_id} -> AnalysisComparison
GET  /api/analyses/{id}/export?format=json|md|html -> file download
POST /api/analyses/{id}/checks/{check_id}/explain {mode: "explain"|"fix"|"expected", provider: "template"|"ai"} -> Explanation
GET  /api/analyses/{id}/checks/{check_id}/ai-payload?mode= -> the exact minimal payload that WOULD be sent (consent preview)
POST /api/demo/load {variant: "buggy"|"fixed"}  -> {subject: SubjectView, project: ProjectView}
```
`python -m premoulinette` serves the API on 127.0.0.1:8765 and, if `frontend/dist` exists, the built SPA at `/`.
Data dir: env `PREMOULINETTE_DATA` or `<repo>/.data/` (gitignored): `premoulinette.db`, `subjects/`, `snapshots/`.

## Diagnosis codes (shared registry — `CheckResult.diagnosis`)

Producers MUST use these codes; `explain/templates.py` MUST have FR+EN templates for each.

| Area | Codes |
|---|---|
| structure | `missing_file`, `misplaced_file`, `wrong_case_path`, `parasite_file`, `missing_gitignore`, `extra_file`, `missing_bonus_file` |
| syntax | `syntax_error`, `indentation_error`, `encoding_error` |
| functions (static) | `missing_function`, `wrong_function_name`, `function_in_wrong_file`, `wrong_param_count`, `wrong_param_names`, `wrong_annotation`, `prints_instead_of_returns`, `str_instead_of_bool`, `nested_function` |
| tests (runtime) | `wrong_value`, `wrong_type`, `str_instead_of_bool`, `number_as_str`, `int_instead_of_float`, `returns_none`, `prints_instead_of_returns`, `wrong_string`, `exception`, `timeout`, `output_limit`, `blocked_syscall`, `unexpected_stdout` |
| output (scripts) | `stdout_mismatch`, `prompt_mismatch`, `missing_prompt`, `missing_output`, `extra_output`, `exit_code`, `script_crash`, `eof_error` |
| constraints | `forbidden_builtin`, `builtin_not_allowed`, `forbidden_import`, `forbidden_method`, `forbidden_construct`, `missing_required_construct`, `builtin_bypass` |
| runtime (import) | `import_side_effects`, `import_crash`, `import_waits_input` |
| git | `untracked_file`, `ignored_file`, `dirty_tree` |
| bonus | `bonus_not_implemented` |

## Harness I/O event convention

`input(prompt)` in the child produces, in order: `RawEvent(kind="output", text=prompt, file, line)` (only if prompt is
non-empty; `line` = line of the `input(...)` call) then `RawEvent(kind="input", text=<line read, without "\n">, file, line)`.
If stdin is exhausted the child raises `EOFError` (no input event). `print(...)` to stdout produces one
`RawEvent(kind="output", text=<exact text written incl. end>, file, line)`. Writes to stderr produce `kind="stderr"` events.
A *prompt* = an output event immediately followed by an input event with the same file/line.
stdout is always written with `\n` newlines (never `\r\n`, even on Windows) and UTF-8.

## Scoring rule (precise)

mandatory checks = `mandatory=True` and status ∈ {pass, warning, fail, skipped}; passed = pass + warning.
`readiness = mandatory_readiness`. Heuristic tests are `mandatory=False` (shown as warnings, they only lower confidence).
Bonus checks are `mandatory=False, bonus=True`.

## Security model (summary)

* Student code is only executed inside the sandbox (Docker safe mode preferred; local developer mode needs explicit acknowledgement).
* Static analysis never executes code. The oracle never uses eval. Git commands run with sanitized config, read-only.
* ZIP ingestion: zip-slip/absolute paths/symlinks rejected, size & count limits.
* API bound to 127.0.0.1, Host check (DNS rebinding), custom header (CSRF), strict CORS.
* AI calls: opt-in, minimal payload, previewable; the full repository is never sent.
