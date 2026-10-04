/**
 * Pure derivations over an AnalysisReport (no React): issue grouping, filters, test rows,
 * file scores, tree flattening. Everything here is unit-tested.
 */
import { compareChecks, SEVERITY_RANK } from '@/lib/check-meta'
import { basename } from '@/lib/format'
import type {
  AnalysisListItem,
  AnalysisReport,
  Category,
  CheckResult,
  FileScore,
  Provenance,
  Severity,
  Status,
  TreeEntry,
} from '@/lib/types'

// ---- issues ---------------------------------------------------------------------------------

/** Same definition as the backend report (report/common.py `is_issue`). */
export const ISSUE_STATUSES: ReadonlySet<Status> = new Set<Status>(['fail', 'skipped', 'bonus', 'warning'])

export function isIssue(check: CheckResult): boolean {
  return ISSUE_STATUSES.has(check.status)
}

/** A blocking issue: counts against the mandatory readiness. */
export function isMandatoryFailure(check: CheckResult): boolean {
  return check.mandatory && !check.bonus && (check.status === 'fail' || check.status === 'skipped')
}

export type StatusFilter = 'fail' | 'warning' | 'bonus' | 'info'

export const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'fail', label: 'Fail' },
  { value: 'warning', label: 'Warning' },
  { value: 'bonus', label: 'Bonus' },
  { value: 'info', label: 'Info' },
]

/** Filter bucket of a status (skipped = could not run = counted as a failure). */
export function statusFilterOf(status: Status): StatusFilter | null {
  switch (status) {
    case 'fail':
    case 'skipped':
      return 'fail'
    case 'warning':
      return 'warning'
    case 'bonus':
      return 'bonus'
    case 'info':
      return 'info'
    default:
      return null
  }
}

export interface IssueFilters {
  statuses: StatusFilter[]
  severity: Severity | 'all'
  provenance: Provenance | 'all'
  query: string
}

export const DEFAULT_ISSUE_FILTERS: IssueFilters = {
  statuses: ['fail', 'warning', 'bonus'],
  severity: 'all',
  provenance: 'all',
  query: '',
}

function haystack(check: CheckResult): string {
  return [
    check.title,
    check.message,
    check.id,
    check.file,
    check.location?.file,
    check.function,
    check.exercise_id,
    check.diagnosis,
  ]
    .filter(Boolean)
    .join('\n')
    .toLowerCase()
}

export function matchesQuery(check: CheckResult, query: string): boolean {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (terms.length === 0) return true
  const text = haystack(check)
  return terms.every((t) => text.includes(t))
}

export function matchesIssueFilters(check: CheckResult, filters: IssueFilters): boolean {
  const bucket = statusFilterOf(check.status)
  if (!bucket || !filters.statuses.includes(bucket)) return false
  if (filters.severity !== 'all' && check.severity !== filters.severity) return false
  if (filters.provenance !== 'all' && check.origin.provenance !== filters.provenance) return false
  return matchesQuery(check, filters.query)
}

/** Key a check is grouped under: the spec file it is about, else where it was found. */
export function checkFileKey(check: CheckResult): string | null {
  return check.file ?? check.location?.file ?? null
}

export const GENERAL_GROUP_LABEL = 'Project-wide'

export interface FileGroup {
  /** File path, or "" for project-wide checks. */
  key: string
  file: string | null
  label: string
  checks: CheckResult[]
  score: FileScore | null
}

export function fileScoreFor(
  path: string | null,
  files: FileScore[],
  detectedRoot: string | null = null,
): FileScore | null {
  if (!path) return null
  const exact = files.find((f) => f.file === path)
  if (exact) return exact
  const root = detectedRoot?.replace(/\/+$/, '')
  if (root && path.startsWith(`${root}/`)) {
    const stripped = path.slice(root.length + 1)
    return files.find((f) => f.file === stripped) ?? null
  }
  return null
}

/**
 * Issues grouped by file. Groups are ordered worst first (status, then severity), then by number of
 * issues and path; checks inside a group are sorted worst first. Project-wide checks come last on ties.
 */
export function groupIssuesByFile(
  checks: CheckResult[],
  files: FileScore[] = [],
  detectedRoot: string | null = null,
): FileGroup[] {
  const groups = new Map<string, CheckResult[]>()
  for (const check of checks) {
    const key = checkFileKey(check) ?? ''
    const list = groups.get(key)
    if (list) list.push(check)
    else groups.set(key, [check])
  }
  const result: FileGroup[] = [...groups.entries()].map(([key, list]) => ({
    key,
    file: key || null,
    label: key ? basename(key) : GENERAL_GROUP_LABEL,
    checks: [...list].sort(compareChecks),
    score: fileScoreFor(key || null, files, detectedRoot),
  }))
  return result.sort((a, b) => {
    const worst = compareChecks(a.checks[0] as CheckResult, b.checks[0] as CheckResult)
    if (worst) return worst
    if (a.checks.length !== b.checks.length) return b.checks.length - a.checks.length
    if (!a.key) return 1
    if (!b.key) return -1
    return a.key.localeCompare(b.key)
  })
}

/** Most important blocking issues first (critical/major mandatory failures), then the rest. */
export function topIssues(checks: CheckResult[], limit = 5): CheckResult[] {
  return checks
    .filter(isIssue)
    .sort((a, b) => {
      const ma = Number(isMandatoryFailure(b)) - Number(isMandatoryFailure(a))
      if (ma) return ma
      const sa = a.severity ? SEVERITY_RANK[a.severity] : 9
      const sb = b.severity ? SEVERITY_RANK[b.severity] : 9
      if (sa !== sb) return sa - sb
      return compareChecks(a, b)
    })
    .slice(0, limit)
}

// ---- tests ----------------------------------------------------------------------------------

export const TEST_CATEGORIES: ReadonlySet<Category> = new Set<Category>([
  'explicit_tests',
  'derived_tests',
  'heuristic_tests',
  'output',
])

export function isTestCheck(check: CheckResult): boolean {
  return TEST_CATEGORIES.has(check.category)
}

export type TestOrigin = 'explicit' | 'derived' | 'heuristic'

export const TEST_ORIGINS: Array<{ value: TestOrigin; label: string; description: string }> = [
  {
    value: 'explicit',
    label: 'Explicit',
    description: 'Examples and terminal sessions written literally in the subject.',
  },
  {
    value: 'derived',
    label: 'Derived',
    description: 'Boundary cases deduced deterministically from an explicit rule of the subject.',
  },
  {
    value: 'heuristic',
    label: 'Heuristic',
    description: 'Extra edge cases (0, negatives, empty strings…). Not official: they only lower confidence.',
  },
]

export function testOrigin(check: CheckResult): TestOrigin {
  if (check.category === 'heuristic_tests' || check.origin.provenance === 'heuristic') return 'heuristic'
  if (check.category === 'derived_tests' || check.origin.provenance === 'derived') return 'derived'
  return 'explicit'
}

export type TestStatusFilter = 'all' | 'failing' | 'passing'

export function matchesTestStatus(check: CheckResult, filter: TestStatusFilter): boolean {
  if (filter === 'all') return true
  const passing = check.status === 'pass' || check.status === 'info'
  return filter === 'passing' ? passing : !passing
}

/** "kelvin.to_kelvin(0)" / "python3 launch_sequence.py (session 1)" / test id. */
export function testCallLabel(check: CheckResult): string {
  const ev = check.evidence
  if (ev?.call) return ev.call
  const session = check.test_id?.match(/#session(\d+)$/)
  const file = check.location?.file ?? check.file
  if (session && file) {
    const args = ev?.argv?.length ? ` ${ev.argv.join(' ')}` : ''
    return `python3 ${basename(file)}${args} · session ${session[1]}`
  }
  return check.test_id ?? check.title
}

export interface ShortValues {
  expected: string | null
  actual: string | null
}

const SHORT_MAX = 80

function clip(text: string | null | undefined): string | null {
  if (text === null || text === undefined) return null
  return text.length > SHORT_MAX ? `${text.slice(0, SHORT_MAX - 1)}…` : text
}

/** One-line expected vs actual summary for the tests table. */
export function shortValues(check: CheckResult): ShortValues {
  const ev = check.evidence
  if (!ev) return { expected: null, actual: null }
  const failure = ev.exception
    ? `${ev.exception.type}${ev.exception.message ? `: ${ev.exception.message}` : ''}`
    : ev.timed_out
      ? 'timeout'
      : null
  if (ev.expected_value || ev.actual_value) {
    return { expected: clip(ev.expected_value?.repr), actual: clip(ev.actual_value?.repr ?? failure) }
  }
  const diff = ev.stdout_diff ?? ev.value_diff
  if (diff) {
    if (diff.equal) return { expected: 'output matches', actual: 'output matches' }
    const line = diff.lines.find((l) => l.op !== 'equal')
    if (line) {
      const label = (text: string | null, no: number | null) =>
        text === null ? '(no line)' : `${no ? `L${no}: ` : ''}${JSON.stringify(text)}`
      return {
        expected: clip(label(line.expected, line.expected_lineno)),
        actual: clip(failure ?? label(line.actual, line.actual_lineno)),
      }
    }
  }
  return { expected: null, actual: clip(failure) }
}

// ---- files ----------------------------------------------------------------------------------

export interface TreeRow {
  entry: TreeEntry
  depth: number
  name: string
  /** Parent directory paths, outermost first. */
  ancestors: string[]
}

/** Flattens the (sorted) tree into indented rows; parents are inserted when the listing omits them. */
export function buildTreeRows(entries: TreeEntry[]): TreeRow[] {
  const byPath = new Map(entries.map((e) => [e.path.replace(/\/+$/, ''), e]))
  for (const entry of entries) {
    const parts = entry.path.replace(/\/+$/, '').split('/')
    for (let i = 1; i < parts.length; i += 1) {
      const dir = parts.slice(0, i).join('/')
      if (!byPath.has(dir)) {
        byPath.set(dir, {
          path: dir,
          kind: 'directory',
          size: null,
          status: 'ok',
          required: null,
          bonus: false,
          git: null,
          note: null,
        })
      }
    }
  }
  const paths = [...byPath.keys()].sort((a, b) => {
    // Directories before files at the same level, then case-sensitive-ish alphabetical order.
    const pa = a.split('/')
    const pb = b.split('/')
    const n = Math.min(pa.length, pb.length)
    for (let i = 0; i < n; i += 1) {
      if (pa[i] === pb[i]) continue
      const aIsDir = i < pa.length - 1 || byPath.get(a)?.kind === 'directory'
      const bIsDir = i < pb.length - 1 || byPath.get(b)?.kind === 'directory'
      if (aIsDir !== bIsDir) return aIsDir ? -1 : 1
      return (pa[i] as string).localeCompare(pb[i] as string)
    }
    return pa.length - pb.length
  })
  return paths.map((path) => {
    const parts = path.split('/')
    return {
      entry: byPath.get(path) as TreeEntry,
      depth: parts.length - 1,
      name: parts[parts.length - 1] ?? path,
      ancestors: parts.slice(0, -1).map((_, i) => parts.slice(0, i + 1).join('/')),
    }
  })
}

// ---- history --------------------------------------------------------------------------------

/** Analyses of the same (subject, project) pair, oldest first. */
export function chronological(items: AnalysisListItem[]): AnalysisListItem[] {
  return [...items].sort((a, b) => a.number - b.number || a.created_at.localeCompare(b.created_at))
}

/** The analysis just before `report` in its history (null for the first one). */
export function previousAnalysis(items: AnalysisListItem[], current: Pick<AnalysisReport, 'id' | 'number'>) {
  const older = chronological(items).filter((i) => i.id !== current.id && i.number < current.number)
  return older[older.length - 1] ?? null
}

// ---- misc -----------------------------------------------------------------------------------

/** vscode://file/<abs path>:<line> for a snapshot-relative file of a local project. */
export function vscodeUrl(projectPath: string | null, file: string, line: number | null): string | null {
  if (!projectPath) return null
  const root = projectPath.replace(/\\/g, '/').replace(/\/+$/, '')
  const rel = file.replace(/\\/g, '/').replace(/^\/+/, '')
  const full = `${root}/${rel}`.replace(/^\/+/, '')
  return `vscode://file/${encodeURI(full)}${line ? `:${line}` : ''}`
}
