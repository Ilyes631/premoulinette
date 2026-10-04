/**
 * Mirror of backend/premoulinette/results/models.py (checks, diffs, scores, reports).
 * Datetimes are ISO 8601 strings in JSON.
 */
import type { Origin, PracticalSpec } from './spec'

export type Status = 'pass' | 'fail' | 'warning' | 'info' | 'bonus' | 'skipped'

export type Severity = 'critical' | 'major' | 'minor' | 'style'

export type Category =
  | 'structure'
  | 'syntax'
  | 'functions'
  | 'explicit_tests'
  | 'derived_tests'
  | 'heuristic_tests'
  | 'output'
  | 'constraints'
  | 'runtime'
  | 'git'

export interface Location {
  file: string
  line: number | null
  end_line: number | null
  /** 0-based column (as in ast) */
  col: number | null
}

export interface CodeExcerpt {
  file: string
  start_line: number
  lines: string[]
  /** Absolute line numbers to highlight */
  highlight: number[]
}

export interface ValueSnapshot {
  repr: string
  type: string
}

export type DiffSegmentOp = 'equal' | 'insert' | 'delete' | 'replace'

export interface DiffSegment {
  op: DiffSegmentOp
  expected: string
  actual: string
}

export type DiffLineOp = 'equal' | 'changed' | 'missing' | 'extra'

export interface DiffLine {
  op: DiffLineOp
  expected_lineno: number | null
  actual_lineno: number | null
  /** Line text WITHOUT its terminator */
  expected: string | null
  actual: string | null
  /** "\n", "\r\n" or "" (no terminator) */
  expected_eol: string
  actual_eol: string
  /** Char-level segments, only for op === "changed" */
  segments: DiffSegment[]
  hints: string[]
  source: Location | null
}

export type DiffKind =
  | 'identical'
  | 'typo'
  | 'case'
  | 'whitespace'
  | 'trailing_whitespace'
  | 'missing_newline'
  | 'extra_newline'
  | 'crlf'
  | 'missing_lines'
  | 'extra_lines'
  | 'different'

export interface TextDiff {
  expected: string
  actual: string
  equal: boolean
  lines: DiffLine[]
  kinds: DiffKind[]
  summary: string
  first_difference: number | null
}

export interface ExceptionInfo {
  type: string
  message: string
  traceback: string
  location: Location | null
}

export interface TranscriptEvent {
  kind: 'output' | 'input' | 'stderr'
  text: string
  location: Location | null
}

export interface Evidence {
  call: string | null
  argv: string[] | null
  stdin: string | null
  expected_value: ValueSnapshot | null
  actual_value: ValueSnapshot | null
  value_diff: TextDiff | null
  stdout_diff: TextDiff | null
  expected_stdout: string | null
  actual_stdout: string | null
  stderr: string | null
  exit_code: number | null
  exception: ExceptionInfo | null
  timed_out: boolean
  duration_ms: number | null
  transcript: TranscriptEvent[] | null
  /** InteractionStep dumps: { kind: "output" | "input", text } */
  expected_steps: Array<Record<string, string>> | null
  rule: string | null
  code: CodeExcerpt | null
  details: Record<string, unknown>
}

export interface Fix {
  summary: string
  file: string | null
  /** Unified diff, minimal hunk */
  patch: string | null
  before: string | null
  after: string | null
  confidence: 'high' | 'medium' | 'low'
}

export interface CheckResult {
  /** Stable across analyses (used by history comparison) */
  id: string
  category: Category
  status: Status
  severity: Severity | null
  title: string
  message: string
  diagnosis: string | null
  exercise_id: string | null
  function: string | null
  test_id: string | null
  file: string | null
  location: Location | null
  origin: Origin
  mandatory: boolean
  bonus: boolean
  blocked_by: string | null
  evidence: Evidence | null
  fix: Fix | null
  tags: string[]
}

// ---------------------------------------------------------------------------------------------
// Project / environment summaries
// ---------------------------------------------------------------------------------------------

export interface GitInfo {
  is_repo: boolean
  branch: string | null
  head: string | null
  last_commit_message: string | null
  last_commit_date: string | null
  dirty: boolean
  modified: string[]
  untracked: string[]
  staged: string[]
  ignored_required: string[]
  remote_url: string | null
  tags: string[]
  error: string | null
}

export type TreeEntryStatus = 'expected' | 'missing' | 'extra' | 'parasite' | 'misplaced' | 'ok'

export interface TreeEntry {
  path: string
  kind: 'file' | 'directory'
  size: number | null
  status: TreeEntryStatus
  required: boolean | null
  bonus: boolean
  git: 'tracked' | 'untracked' | 'modified' | 'ignored' | null
  note: string | null
}

export type SandboxMode = 'docker' | 'local'

export interface SandboxInfo {
  mode: SandboxMode
  image: string | null
  python_version: string | null
  network: boolean
  limits: Record<string, unknown>
  warnings: string[]
}

// ---------------------------------------------------------------------------------------------
// Scores
// ---------------------------------------------------------------------------------------------

export interface CategoryScore {
  key: string
  label: string
  passed: number
  total: number
  /** 0..100, null if total === 0 */
  score: number | null
  failed: number
  warnings: number
}

export type ExerciseScoreStatus = 'pass' | 'fail' | 'warning' | 'missing' | 'not_implemented' | 'partial'

export interface ExerciseScore {
  exercise_id: string
  title: string
  file: string
  bonus: boolean
  required: boolean
  status: ExerciseScoreStatus
  passed: number
  total: number
  score: number | null
  issues: number
}

export interface FileScore {
  file: string
  exercise_ids: string[]
  present: boolean
  passed: number
  total: number
  score: number | null
  issues: number
  worst_severity: Severity | null
}

export type Verdict = 'ready' | 'not_ready'
export type Confidence = 'high' | 'medium' | 'low'

export interface ScoreSummary {
  readiness: number
  mandatory_readiness: number
  mandatory_passed: number
  mandatory_total: number
  mandatory_failures: number
  bonus_completion: number | null
  bonus_passed: number
  bonus_total: number
  confidence: Confidence
  confidence_reasons: string[]
  categories: CategoryScore[]
  exercises: ExerciseScore[]
  files: FileScore[]
  /** By status, and "critical" / "major" / ... by severity */
  counts: Record<string, number>
  verdict: Verdict
  verdict_title: string
  verdict_message: string
}

export interface SubjectSummary {
  id: string
  title: string
  source_name: string | null
  language: string
  parser: string
}

export type ProjectSourceKind = 'path' | 'zip' | 'upload' | 'demo'

export interface ProjectSummary {
  id: string
  name: string
  source_kind: ProjectSourceKind
  path: string | null
  detected_root: string | null
  root_note: string | null
  file_count: number
  python_files: number
  git: GitInfo | null
}

export interface AnalysisReport {
  id: string
  number: number
  created_at: string
  duration_ms: number
  subject: SubjectSummary
  project: ProjectSummary
  sandbox: SandboxInfo
  spec: PracticalSpec
  checks: CheckResult[]
  tree: TreeEntry[]
  score: ScoreSummary
  pipeline_warnings: string[]
}

export interface AnalysisListItem {
  id: string
  number: number
  created_at: string
  subject_id: string
  project_id: string
  subject_title: string
  project_name: string
  readiness: number
  mandatory_readiness: number
  bonus_completion: number | null
  verdict: Verdict
  mandatory_failures: number
}

export interface CheckChange {
  id: string
  title: string
  file: string | null
  before: Status | null
  after: Status | null
}

export interface AnalysisComparison {
  base_id: string
  head_id: string
  readiness_delta: number
  fixed: CheckChange[]
  new_failures: CheckChange[]
  still_failing: CheckChange[]
  new_checks: CheckChange[]
  removed_checks: CheckChange[]
}
