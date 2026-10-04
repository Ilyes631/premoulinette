/**
 * Typed client for every endpoint of the PréMoulinette REST API (ARCHITECTURE.md).
 *
 * - All paths live under `/api` (proxied to 127.0.0.1:8765 by Vite in development; same origin
 *   when the SPA is served by `python -m premoulinette`).
 * - Mutating requests always carry `X-PreMoulinette: 1` (the backend's CSRF guard).
 * - Non-2xx responses become an {@link ApiError} carrying the JSON `detail`.
 * - In the online demo build (VITE_DEMO=1) the same functions are served by the static transport
 *   of `./demo` instead of `fetch` (one code path for every caller).
 */
import { ApiError, formatErrorDetail } from './api-error'
import { demoTransport, IS_DEMO } from './demo'
import type {
  AnalysisComparison,
  AnalysisListItem,
  AnalysisReport,
  DemoLoadResult,
  DemoVariant,
  ExplainMode,
  ExplainRequest,
  Explanation,
  ExplanationLanguage,
  ExportFormat,
  Health,
  JobRef,
  JobState,
  PracticalSpec,
  ProjectFile,
  ProjectListItem,
  ProjectView,
  Settings,
  SettingsUpdate,
  StartAnalysisRequest,
  SubjectDocumentView,
  SubjectTests,
  SubjectView,
} from './types'
import { folderNameOf, relativePathOf } from './uploads'

export { ApiError, errorMessage, formatErrorDetail, isApiError } from './api-error'
export { DemoReadOnlyError, isDemoReadOnlyError } from './demo'

export const API_BASE = '/api'
export const CSRF_HEADER = 'X-PreMoulinette'

const OFFLINE_MESSAGE =
  'PréMoulinette is not running. Double-click start.bat (keep its black window open), wait 10 seconds, then retry.'

// ---------------------------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------------------------

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
type QueryValue = string | number | boolean | null | undefined

export interface RequestOptions {
  method?: Method
  /** JSON body (serialized, sets Content-Type). */
  json?: unknown
  /** Multipart body (Content-Type left to the browser for the boundary). */
  form?: FormData
  query?: Record<string, QueryValue>
  signal?: AbortSignal
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function toApiError(res: Response): Promise<ApiError> {
  let detail: unknown = null
  try {
    const text = await res.text()
    if (text) {
      try {
        const body: unknown = JSON.parse(text)
        detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : body
      } catch {
        detail = text
      }
    }
  } catch {
    // body unreadable: keep detail null
  }
  const fallback = `${res.status} ${res.statusText || 'Request failed'}`.trim()
  return new ApiError(res.status, formatErrorDetail(detail) ?? fallback, detail)
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  if (IS_DEMO) {
    const { json, form, query, signal } = options
    return demoTransport().request<T>({ method, path, json, form, query, signal })
  }
  const headers = new Headers({ Accept: 'application/json' })
  if (method !== 'GET') headers.set(CSRF_HEADER, '1')

  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.json)
  } else if (options.form) {
    body = options.form
  }

  let res: Response
  try {
    res = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      signal: options.signal,
      credentials: 'same-origin',
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, OFFLINE_MESSAGE, null)
  }

  if (!res.ok) throw await toApiError(res)
  if (res.status === 204) return undefined as T
  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('json')) return (await res.json()) as T
  return (await res.text()) as unknown as T
}

const enc = encodeURIComponent

// ---------------------------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------------------------

export const getHealth = (signal?: AbortSignal) => apiRequest<Health>('/health', { signal })

export const getSettings = () => apiRequest<Settings>('/settings')
export const updateSettings = (patch: SettingsUpdate) =>
  apiRequest<Settings>('/settings', { method: 'PUT', json: patch })

export const prepareSandbox = () => apiRequest<JobRef>('/sandbox/prepare', { method: 'POST' })

// ---- subjects ----
export function uploadSubject(file: File): Promise<SubjectView> {
  const form = new FormData()
  form.append('file', file, file.name)
  return apiRequest<SubjectView>('/subjects', { method: 'POST', form })
}
export const reparseSubject = (id: string, useAi: boolean) =>
  apiRequest<SubjectView>(`/subjects/${enc(id)}/reparse`, { method: 'POST', json: { use_ai: useAi } })
export const listSubjects = () => apiRequest<SubjectView[]>('/subjects')
export const getSubject = (id: string) => apiRequest<SubjectView>(`/subjects/${enc(id)}`)
export const updateSpec = (id: string, spec: PracticalSpec) =>
  apiRequest<SubjectView>(`/subjects/${enc(id)}/spec`, { method: 'PUT', json: spec })
export const getSubjectTests = (id: string) => apiRequest<SubjectTests>(`/subjects/${enc(id)}/tests`)
export const getSubjectDocument = (id: string) =>
  apiRequest<SubjectDocumentView>(`/subjects/${enc(id)}/document`)
export const getSpecSchema = () => apiRequest<Record<string, unknown>>('/spec/schema')

// ---- projects ----
export function createProjectFromPath(path: string): Promise<ProjectView> {
  const form = new FormData()
  form.append('path', path)
  return apiRequest<ProjectView>('/projects', { method: 'POST', form })
}
export function createProjectFromZip(file: File): Promise<ProjectView> {
  const form = new FormData()
  form.append('file', file, file.name)
  return apiRequest<ProjectView>('/projects', { method: 'POST', form })
}
/** Folder picked with `<input webkitdirectory>`: one `files` + one `paths` entry per file. */
export function createProjectFromFolder(files: File[], name?: string): Promise<ProjectView> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file, file.name)
    form.append('paths', relativePathOf(file))
  }
  const folder = name ?? folderNameOf(files)
  if (folder) form.append('name', folder)
  return apiRequest<ProjectView>('/projects', { method: 'POST', form })
}
export const listProjects = () => apiRequest<ProjectListItem[]>('/projects')
export const getProject = (id: string) => apiRequest<ProjectView>(`/projects/${enc(id)}`)
export const getProjectFile = (id: string, path: string) =>
  apiRequest<ProjectFile>(`/projects/${enc(id)}/file`, { query: { path } })

// ---- analyses & jobs ----
export const startAnalysis = (req: StartAnalysisRequest) =>
  apiRequest<JobRef>('/analyses', { method: 'POST', json: req })
export const getJob = (id: string, signal?: AbortSignal) => apiRequest<JobState>(`/jobs/${enc(id)}`, { signal })

export interface ListAnalysesParams {
  subject_id?: string
  project_id?: string
  limit?: number
}
export const listAnalyses = (params: ListAnalysesParams = {}) =>
  apiRequest<AnalysisListItem[]>('/analyses', { query: { ...params } })
export const getAnalysis = (id: string) => apiRequest<AnalysisReport>(`/analyses/${enc(id)}`)
export const compareAnalyses = (id: string, baseId: string) =>
  apiRequest<AnalysisComparison>(`/analyses/${enc(id)}/compare/${enc(baseId)}`)
/** Plain link for `<a href download>` (GET, no custom header needed; a static file in the demo). */
export const exportUrl = (id: string, format: ExportFormat) =>
  IS_DEMO ? demoTransport().exportUrl(id, format) : buildUrl(`/analyses/${enc(id)}/export`, { format })

// Check ids contain ':', '/' and '#': always encode them (the backend route accepts encoded slashes).
export const explainCheck = (analysisId: string, checkId: string, req: ExplainRequest) =>
  apiRequest<Explanation>(`/analyses/${enc(analysisId)}/checks/${enc(checkId)}/explain`, {
    method: 'POST',
    json: req,
  })
/** The exact minimal payload an AI explanation WOULD send (consent preview; nothing is sent). */
export const getAiPayload = (
  analysisId: string,
  checkId: string,
  mode: Exclude<ExplainMode, 'expected'>,
  lang?: ExplanationLanguage,
) =>
  apiRequest<Record<string, unknown>>(`/analyses/${enc(analysisId)}/checks/${enc(checkId)}/ai-payload`, {
    query: { mode, lang },
  })

// ---- demo ----
/** `reset` re-parses the demo subject (discards edits made to its spec). */
export const loadDemo = (variant: DemoVariant, reset = false) =>
  apiRequest<DemoLoadResult>('/demo/load', { method: 'POST', json: reset ? { variant, reset } : { variant } })

/** Namespace-style access, handy for mocking in tests: `vi.spyOn(api, 'getJob')`. */
export const api = {
  getHealth,
  getSettings,
  updateSettings,
  prepareSandbox,
  uploadSubject,
  reparseSubject,
  listSubjects,
  getSubject,
  updateSpec,
  getSubjectTests,
  getSubjectDocument,
  getSpecSchema,
  createProjectFromPath,
  createProjectFromZip,
  createProjectFromFolder,
  listProjects,
  getProject,
  getProjectFile,
  startAnalysis,
  getJob,
  listAnalyses,
  getAnalysis,
  compareAnalyses,
  exportUrl,
  explainCheck,
  getAiPayload,
  loadDemo,
}
