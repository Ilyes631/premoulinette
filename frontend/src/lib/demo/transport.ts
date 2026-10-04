/**
 * Static transport of the online demo: answers the API calls of `api.ts` from the JSON files of
 * `public/demo-data` (exported from the real API by `backend/scripts/export_demo_data.py`).
 *
 * - GET: the recorded response of the manifest route (a recorded error, or a 404, otherwise).
 * - POST /api/demo/load: the recorded response for the variant.
 * - POST /api/analyses: a simulated job (`job-sim.ts`). The first analysis of the buggy demo
 *   project is its Analysis #1, any later one its Analysis #2 (the "fixed" run); analyses only
 *   appear in lists once they were run (or opened by a link), with "now" as their date.
 * - POST .../explain: the recorded template explanation (other language as a fallback).
 * - Everything else (uploads, local folders, saving settings or the contract, AI, Docker)
 *   rejects with a {@link DemoReadOnlyError}.
 *
 * The state (finished analyses, running jobs) lives in memory and in the given storage
 * (sessionStorage in the app): a new tab starts the demo over.
 */
import { ApiError, formatErrorDetail } from '../api-error'
import type {
  AnalysisListItem,
  AnalysisReport,
  ExplainMode,
  ExplainRequest,
  Explanation,
  JobRef,
  JobState,
  Settings,
  StartAnalysisRequest,
} from '../types'
import { DemoReadOnlyError } from './errors'
import { DEMO_JOB_DURATION_MS, simulateJob, type SimulatedJob } from './job-sim'
import {
  decodePath,
  pickResponse,
  requestKey,
  type DemoManifest,
  type ManifestResponse,
  type QueryValue,
} from './manifest'

export interface DemoRequest {
  method?: string
  /** Path relative to `/api`, as given to `apiRequest` (segments may be URL-encoded). */
  path: string
  query?: Record<string, QueryValue>
  json?: unknown
  form?: FormData
  signal?: AbortSignal
}

export interface DemoTransportOptions {
  /** URL of the demo data folder, e.g. "/demo-data/". */
  baseUrl: string
  fetch?: (input: string, init?: RequestInit) => Promise<Response>
  /** Where the demo state survives reloads (sessionStorage in the app). */
  storage?: Pick<Storage, 'getItem' | 'setItem'> | null
  now?: () => number
  sleep?: (ms: number) => Promise<void>
  jobDurationMs?: number
  /** Artificial latency (ms) of the demo loader and of starting an analysis, for a natural feel. */
  latencyMs?: { demoLoad: number; start: number }
}

export interface DemoTransport {
  request<T>(req: DemoRequest): Promise<T>
  /** Static download URL of a report export. */
  exportUrl(analysisId: string, format: string): string
}

export const DEMO_STATE_KEY = 'premoulinette.demo.state'
const MAX_JOBS = 20
/** Analyses implied by a link (#1 when #2 is opened) are dated a few minutes before it. */
const EARLIER_RUN_GAP_MS = 3 * 60_000
const DEFAULT_LIST_LIMIT = 50
const DATA_UNAVAILABLE = 'Could not load the demo data. Check your connection and retry.'
const NOT_IN_DEMO = 'This is not part of the online demo.'
const EXPLAIN_RE = /^\/api\/analyses\/([^/]+)\/checks\/(.+)\/explain$/

interface DemoState {
  /** Analysis id -> epoch ms shown as its date. Analyses not listed have not been run yet. */
  done: Record<string, number>
  jobs: Record<string, SimulatedJob>
  seq: number
}

type ExplainBundle = Record<string, Partial<Record<ExplainMode, Explanation>>>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function throwIfAborted(signal: AbortSignal | undefined): void {
  if (signal?.aborted) throw new DOMException('The operation was aborted.', 'AbortError')
}

/** What a rejected request would have done, for the read-only notice. */
export function readOnlyAction(method: string, path: string, form?: FormData): string {
  if (path === '/api/subjects') return 'Importing a subject'
  if (path === '/api/projects') {
    if (form?.has('path')) return 'Analyzing a local folder'
    if (form?.has('files')) return 'Uploading a folder'
    return 'Importing a project'
  }
  if (/^\/api\/subjects\/[^/]+\/reparse$/.test(path)) return 'Re-parsing a subject'
  if (/^\/api\/subjects\/[^/]+\/spec$/.test(path)) return 'Saving the contract'
  if (path === '/api/settings') return 'Saving settings'
  if (path === '/api/sandbox/prepare') return 'Preparing the Docker sandbox'
  if (path.endsWith('/ai-payload') || EXPLAIN_RE.test(path)) return 'AI explanations'
  return method === 'GET' ? 'This feature' : 'Changing data'
}

export function createDemoTransport(options: DemoTransportOptions): DemoTransport {
  const base = options.baseUrl.endsWith('/') ? options.baseUrl : `${options.baseUrl}/`
  const fetchImpl = options.fetch ?? ((input: string, init?: RequestInit) => fetch(input, init))
  const now = options.now ?? (() => Date.now())
  const sleep = options.sleep ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)))
  const jobDurationMs = options.jobDurationMs ?? DEMO_JOB_DURATION_MS
  const latency = options.latencyMs ?? { demoLoad: 450, start: 150 }
  const storage = options.storage ?? null

  const files = new Map<string, Promise<unknown>>()
  let manifestPromise: Promise<DemoManifest> | null = null
  let state: DemoState | null = null

  // ---- state ----------------------------------------------------------------------------------

  function loadState(): DemoState {
    if (state) return state
    let saved: unknown = null
    try {
      const raw = storage?.getItem(DEMO_STATE_KEY)
      saved = raw ? JSON.parse(raw) : null
    } catch {
      saved = null
    }
    const s = isRecord(saved) ? saved : {}
    state = {
      done: isRecord(s.done) ? (s.done as DemoState['done']) : {},
      jobs: isRecord(s.jobs) ? (s.jobs as DemoState['jobs']) : {},
      seq: typeof s.seq === 'number' ? s.seq : 0,
    }
    return state
  }

  function saveState(): void {
    try {
      storage?.setItem(DEMO_STATE_KEY, JSON.stringify(loadState()))
    } catch {
      // storage unavailable or full: the state simply lives in memory
    }
  }

  const isDone = (analysisId: string) => loadState().done[analysisId] !== undefined

  function shownDate(analysisId: string): string | null {
    const at = loadState().done[analysisId]
    return at === undefined ? null : new Date(at).toISOString()
  }

  /** `analysisId` (and the earlier runs of its project) now exist, dated `at`. */
  function markDone(m: DemoManifest, analysisId: string, at: number, redate = false): void {
    const info = m.analyses[analysisId]
    if (!info) return
    const s = loadState()
    const runs = m.runs[info.project_id] ?? [analysisId]
    const index = Math.max(0, runs.indexOf(analysisId))
    runs.slice(0, index).forEach((earlier, i) => {
      if (s.done[earlier] === undefined) s.done[earlier] = at - (index - i) * EARLIER_RUN_GAP_MS
    })
    if (redate || s.done[analysisId] === undefined) s.done[analysisId] = at
    saveState()
  }

  // ---- data files -----------------------------------------------------------------------------

  function loadFile<T>(file: string): Promise<T> {
    let pending = files.get(file)
    if (!pending) {
      pending = (async () => {
        let res: Response
        try {
          res = await fetchImpl(`${base}${file}`, { headers: { Accept: 'application/json' } })
        } catch {
          throw new ApiError(0, DATA_UNAVAILABLE)
        }
        if (!res.ok) throw new ApiError(res.status === 404 ? 404 : 0, res.status === 404 ? NOT_IN_DEMO : DATA_UNAVAILABLE)
        const text = await res.text()
        try {
          return JSON.parse(text) as unknown
        } catch {
          // a static host answering a missing file with the SPA's index.html
          throw new ApiError(404, NOT_IN_DEMO)
        }
      })()
      files.set(file, pending)
      pending.catch(() => files.delete(file))
    }
    return pending as Promise<T>
  }

  function manifest(): Promise<DemoManifest> {
    manifestPromise ??= loadFile<DemoManifest>('manifest.json').catch((error: unknown) => {
      manifestPromise = null
      throw error
    })
    return manifestPromise
  }

  async function respond<T>(entry: ManifestResponse): Promise<T> {
    if (entry.file) return clone(await loadFile<T>(entry.file))
    const status = entry.status ?? 404
    throw new ApiError(status, formatErrorDetail(entry.detail) ?? `${status} Error`, entry.detail ?? null)
  }

  function route<T>(m: DemoManifest, key: string): Promise<T> {
    const value = m.routes[key]
    if (value === undefined) return Promise.reject(new ApiError(404, NOT_IN_DEMO))
    return respond<T>(pickResponse(value, isDone))
  }

  // ---- handlers -------------------------------------------------------------------------------

  async function listAnalyses(m: DemoManifest, query: Record<string, QueryValue> = {}): Promise<AnalysisListItem[]> {
    const value =
      m.routes[requestKey('GET', '/api/analyses', { limit: 1000 })] ??
      m.routes[requestKey('GET', '/api/analyses', query)] ??
      m.routes[requestKey('GET', '/api/analyses')]
    if (value === undefined) return []
    const all = await respond<AnalysisListItem[]>(pickResponse(value, isDone))
    const limit = Math.max(1, Number(query.limit) || DEFAULT_LIST_LIMIT)
    return all
      .filter((item) => !query.subject_id || item.subject_id === query.subject_id)
      .filter((item) => !query.project_id || item.project_id === query.project_id)
      .filter((item) => isDone(item.id))
      .map((item) => ({ ...item, created_at: shownDate(item.id) ?? item.created_at }))
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.number - a.number)
      .slice(0, limit)
  }

  async function getAnalysis(m: DemoManifest, analysisId: string, key: string): Promise<AnalysisReport> {
    const report = await route<AnalysisReport>(m, key)
    markDone(m, analysisId, now()) // opened by a link: from now on it exists
    report.created_at = shownDate(analysisId) ?? report.created_at
    return report
  }

  async function startAnalysis(m: DemoManifest, body: unknown): Promise<JobRef> {
    const req = (isRecord(body) ? body : {}) as Partial<StartAnalysisRequest>
    if (req.subject_id !== m.subject_id) throw new ApiError(404, `Unknown subject '${req.subject_id ?? ''}'`)
    const runs = req.project_id ? m.runs[req.project_id] : undefined
    if (!runs?.length) throw new ApiError(404, `Unknown project '${req.project_id ?? ''}'`)
    await sleep(latency.start)
    const s = loadState()
    const target = runs.find((id) => s.done[id] === undefined) ?? (runs[runs.length - 1] as string)
    const startedAt = now()
    s.seq += 1
    const id = `demo-job-${startedAt.toString(36)}-${s.seq}`
    s.jobs[id] = { id, target, startedAt }
    const stale = Object.values(s.jobs)
      .sort((a, b) => b.startedAt - a.startedAt)
      .slice(MAX_JOBS)
    for (const job of stale) delete s.jobs[job.id]
    // Listed (and dated) as soon as it starts, like a report saved at the end of the run.
    markDone(m, target, startedAt + jobDurationMs, true)
    return { job_id: id }
  }

  function getJob(jobId: string): JobState {
    const job = loadState().jobs[jobId]
    if (!job) throw new ApiError(404, `Unknown job '${jobId}'`)
    return simulateJob(job, now(), jobDurationMs)
  }

  async function explain(m: DemoManifest, analysisId: string, checkId: string, body: unknown): Promise<Explanation> {
    const req = (isRecord(body) ? body : {}) as Partial<ExplainRequest>
    if (req.provider === 'ai') throw new DemoReadOnlyError('AI explanations')
    const mode: ExplainMode = req.mode ?? 'explain'
    const bundles = m.explain[analysisId]
    if (!bundles) throw new ApiError(404, `Unknown analysis '${analysisId}'`)
    let lang: string | undefined = req.lang
    if (!lang) {
      try {
        lang = (await route<Settings>(m, requestKey('GET', '/api/settings'))).explanation_language
      } catch {
        lang = 'fr'
      }
    }
    const languages = [lang, ...Object.keys(bundles).filter((l) => l !== lang)]
    for (const language of languages) {
      const file = bundles[language]
      if (!file) continue
      const found = (await loadFile<ExplainBundle>(file))[checkId]?.[mode]
      if (found) return clone(found)
    }
    throw new ApiError(404, `Unknown check '${checkId}' in analysis '${analysisId}'`)
  }

  async function dispatch(method: string, path: string, req: DemoRequest): Promise<unknown> {
    const explainMatch = EXPLAIN_RE.exec(path)
    const servedPost = path === '/api/demo/load' || path === '/api/analyses' || explainMatch !== null
    if ((method !== 'GET' && !(method === 'POST' && servedPost)) || path.endsWith('/ai-payload')) {
      throw new DemoReadOnlyError(readOnlyAction(method, path, req.form))
    }
    const m = await manifest()
    if (method === 'GET') {
      if (path === '/api/analyses') return listAnalyses(m, req.query)
      const job = /^\/api\/jobs\/([^/]+)$/.exec(path)
      if (job) return getJob(job[1] ?? '')
      const key = requestKey('GET', path, req.query)
      const analysis = /^\/api\/analyses\/([^/]+)$/.exec(path)
      if (analysis) return getAnalysis(m, analysis[1] ?? '', key)
      return route(m, key)
    }
    if (path === '/api/demo/load') {
      await sleep(latency.demoLoad)
      const variant = isRecord(req.json) && typeof req.json.variant === 'string' ? req.json.variant : 'buggy'
      return route(m, requestKey('POST', path, { variant }))
    }
    if (path === '/api/analyses') return startAnalysis(m, req.json)
    return explain(m, explainMatch?.[1] ?? '', explainMatch?.[2] ?? '', req.json)
  }

  return {
    async request<T>(req: DemoRequest): Promise<T> {
      const method = (req.method ?? 'GET').toUpperCase()
      const path = `/api${decodePath(req.path)}`
      throwIfAborted(req.signal)
      const result = await dispatch(method, path, req)
      throwIfAborted(req.signal)
      return result as T
    },
    exportUrl(analysisId: string, format: string): string {
      return `${base}exports/premoulinette-report-${encodeURIComponent(analysisId)}.${format}`
    },
  }
}
