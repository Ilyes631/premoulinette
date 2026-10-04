/**
 * API-level views (ARCHITECTURE.md "REST API" section) and models from non-shared modules
 * (store Settings, sandbox DockerStatus, testgen generated tests, explain Explanation, jobs).
 */
import type { GitInfo, TreeEntry } from './results'
import type { FunctionTest, PracticalSpec, ScriptTest, SpecStats } from './spec'

// ---- sandbox / health ----------------------------------------------------------------------

export interface DockerStatus {
  available: boolean
  version: string | null
  image: string
  image_ready: boolean
  error: string | null
}

export type EffectiveSandboxMode = 'docker' | 'local' | 'none'
export type SandboxPreference = 'auto' | 'docker' | 'local'

export interface Health {
  ok: boolean
  version: string
  python: string
  docker: DockerStatus
  /** The mode chosen in the settings. */
  sandbox_mode?: SandboxPreference
  /** "none" when no sandbox can run (Docker missing and local mode not acknowledged). */
  sandbox_mode_effective: EffectiveSandboxMode | null
  /** Why that mode was chosen (or why nothing can run). */
  sandbox_note?: string | null
  ai: { configured: boolean; enabled: boolean }
}

// ---- settings ------------------------------------------------------------------------------

export type ExplanationLanguage = 'fr' | 'en'

/** Settings as returned by GET/PUT /api/settings (the API key itself is never returned). */
export interface Settings {
  sandbox_mode: SandboxPreference
  local_mode_acknowledged: boolean
  docker_image: string
  ai_enabled: boolean
  ai_model: string
  ai_consent_subject: boolean
  ai_consent_code: boolean
  /** Read-only: an API key is configured (the key itself is never returned). */
  has_api_key: boolean
  /** Read-only: where the key comes from. */
  api_key_source?: 'settings' | 'env' | null
  explanation_language: ExplanationLanguage
  default_timeout_s: number
}

/** Body of PUT /api/settings (partial). `anthropic_api_key`: string sets it, null/"" clears it, absent keeps it. */
export type SettingsUpdate = Partial<Omit<Settings, 'has_api_key' | 'api_key_source'>> & {
  anthropic_api_key?: string | null
}

// ---- subjects ------------------------------------------------------------------------------

export type SubjectMediaType = 'html' | 'markdown' | 'text' | 'pdf'

/** Validation issue reported by spec/validate.py. */
export interface SpecIssue {
  level: 'error' | 'warning'
  /** Path of the offending item, e.g. "exercises[2].functions[0]" */
  path: string
  message: string
}

export interface SubjectView {
  id: string
  title: string
  source_name: string
  created_at: string
  updated_at: string
  parser: string
  media_type: SubjectMediaType
  spec: PracticalSpec
  stats: SpecStats
  warnings: string[]
  validation: SpecIssue[]
}

export interface SubjectDocumentView {
  text: string
  html: string | null
  media_type: SubjectMediaType
}

export type TestCategory = 'explicit_tests' | 'derived_tests' | 'heuristic_tests'

export interface GeneratedFunctionTest {
  test: FunctionTest
  exercise_id: string
  category: TestCategory
  rule: string | null
}

export interface GeneratedScriptTest {
  test: ScriptTest
  exercise_id: string
  category: 'explicit_tests' | 'output'
}

export interface SubjectTests {
  explicit: GeneratedFunctionTest[]
  derived: GeneratedFunctionTest[]
  heuristic: GeneratedFunctionTest[]
  scripts: GeneratedScriptTest[]
}

// ---- projects ------------------------------------------------------------------------------

export type ProjectSourceKindView = 'path' | 'zip' | 'upload' | 'demo'

export interface ProjectView {
  id: string
  name: string
  source_kind: ProjectSourceKindView
  /** Original local folder (path / demo projects): enables one-click re-analysis. */
  source_path: string | null
  created_at: string
  file_count: number
  python_files: number
  tree: TreeEntry[]
  git: GitInfo | null
  language: string
  /** Import notes (skipped heavy folders, limits...). */
  warnings: string[]
}

/** GET /api/projects items. */
export interface ProjectListItem {
  id: string
  name: string
  source_kind: ProjectSourceKindView
  source_path: string | null
  created_at: string
  file_count: number
  python_files: number
}

export interface ProjectFile {
  path: string
  content: string
  language: string
  size?: number
}

export interface DemoLoadResult {
  subject: SubjectView
  project: ProjectView
}

export type DemoVariant = 'buggy' | 'fixed'

// ---- jobs / analyses -----------------------------------------------------------------------

export type JobStatusValue = 'queued' | 'running' | 'done' | 'error'
export type StageStatus = 'pending' | 'running' | 'done' | 'error'

export interface JobStage {
  key: string
  label: string
  status: StageStatus
}

export interface JobState {
  id: string
  /** "analysis" | "sandbox_prepare" */
  kind: string
  status: JobStatusValue
  stage: string | null
  stages: JobStage[]
  /** 0..1 */
  progress: number
  result_id: string | null
  /** User-facing failure message (status "error"). */
  error: string | null
  created_at?: string
  finished_at?: string | null
}

export interface JobRef {
  job_id: string
}

export interface StartAnalysisRequest {
  subject_id: string
  project_id: string
}

export type ExportFormat = 'json' | 'md' | 'html'

// ---- explanations --------------------------------------------------------------------------

export type ExplainMode = 'explain' | 'fix' | 'expected'
export type ExplainProvider = 'template' | 'ai'

/** Body of POST /api/analyses/{id}/checks/{check_id}/explain. */
export interface ExplainRequest {
  mode: ExplainMode
  provider: ExplainProvider
  /** Defaults to the explanation language of the settings. */
  lang?: ExplanationLanguage
}

export interface Explanation {
  title: string
  markdown: string
  provider: ExplainProvider
  language: ExplanationLanguage
  sent_payload: Record<string, unknown> | null
}

/** Body of a FastAPI validation error (422). */
export interface ValidationErrorItem {
  loc: Array<string | number>
  msg: string
  type?: string
}
