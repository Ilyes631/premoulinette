/**
 * Remembers which subject / project an analysis job was started for. The job API only returns
 * stages and progress; this lets the progress page show names and offer "Retry analysis".
 */
export interface JobContext {
  subject_id: string
  project_id: string
  subject_title?: string | null
  project_name?: string | null
}

const STORAGE_KEY = 'premoulinette.jobs'
const MAX_ENTRIES = 30

type JobContextMap = Record<string, JobContext & { at: number }>

function load(): JobContextMap {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as JobContextMap) : {}
  } catch {
    return {}
  }
}

export function rememberJob(jobId: string, context: JobContext): void {
  try {
    const entries = load()
    entries[jobId] = { ...context, at: Date.now() }
    const kept = Object.entries(entries)
      .sort(([, a], [, b]) => (b.at ?? 0) - (a.at ?? 0))
      .slice(0, MAX_ENTRIES)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(kept)))
  } catch {
    // storage unavailable: the progress page just shows fewer details
  }
}

export function recallJob(jobId: string | null | undefined): JobContext | null {
  if (!jobId) return null
  const entry = load()[jobId]
  if (!entry || typeof entry.subject_id !== 'string' || typeof entry.project_id !== 'string') return null
  return {
    subject_id: entry.subject_id,
    project_id: entry.project_id,
    subject_title: entry.subject_title ?? null,
    project_name: entry.project_name ?? null,
  }
}
