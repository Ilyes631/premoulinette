import type { AnalysisListItem } from '@/lib/types'

export interface HistoryRun {
  item: AnalysisListItem
  /** Readiness change vs the previous analysis of the same pair (null for the first one). */
  delta: number | null
}

export interface HistoryGroup {
  key: string
  subjectId: string
  projectId: string
  subjectTitle: string
  projectName: string
  /** Oldest first (chart order). */
  runs: HistoryRun[]
  latest: HistoryRun
}

function time(iso: string): number {
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? 0 : t
}

function chronological(a: AnalysisListItem, b: AnalysisListItem): number {
  return time(a.created_at) - time(b.created_at) || a.number - b.number
}

/** Rounds a readiness delta to one decimal, avoiding "-0". */
export function roundDelta(value: number): number {
  const rounded = Math.round(value * 10) / 10
  return Object.is(rounded, -0) ? 0 : rounded
}

/** Groups analyses by (subject, project), each group oldest → newest; groups sorted by latest activity. */
export function groupAnalyses(items: AnalysisListItem[]): HistoryGroup[] {
  const byPair = new Map<string, AnalysisListItem[]>()
  for (const item of items) {
    const key = `${item.subject_id}::${item.project_id}`
    const list = byPair.get(key)
    if (list) list.push(item)
    else byPair.set(key, [item])
  }
  const groups: HistoryGroup[] = []
  for (const [key, list] of byPair) {
    const sorted = [...list].sort(chronological)
    const runs = sorted.map((item, i) => {
      const prev = i > 0 ? sorted[i - 1] : undefined
      return { item, delta: prev ? roundDelta(item.readiness - prev.readiness) : null }
    })
    const latest = runs[runs.length - 1]
    if (!latest) continue
    groups.push({
      key,
      subjectId: latest.item.subject_id,
      projectId: latest.item.project_id,
      subjectTitle: latest.item.subject_title,
      projectName: latest.item.project_name,
      runs,
      latest,
    })
  }
  return groups.sort((a, b) => time(b.latest.item.created_at) - time(a.latest.item.created_at))
}

export function formatDelta(delta: number | null): string {
  if (delta === null) return 'first run'
  if (delta === 0) return '±0'
  return `${delta > 0 ? '+' : '−'}${Math.abs(delta)}`
}

export function matchesQuery(group: HistoryGroup, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return group.subjectTitle.toLowerCase().includes(q) || group.projectName.toLowerCase().includes(q)
}
