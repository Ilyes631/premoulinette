/** Presentation metadata for check statuses, severities, categories and provenance. */
import type { Category, CheckResult, Provenance, Severity, Status } from './types'

export type Tone = 'pass' | 'fail' | 'warning' | 'info' | 'bonus' | 'skipped' | 'neutral' | 'accent'

export const STATUS_LABELS: Record<Status, string> = {
  pass: 'Pass',
  fail: 'Fail',
  warning: 'Warning',
  info: 'Info',
  bonus: 'Bonus',
  skipped: 'Skipped',
}

export const STATUS_TONES: Record<Status, Tone> = {
  pass: 'pass',
  fail: 'fail',
  warning: 'warning',
  info: 'info',
  bonus: 'bonus',
  skipped: 'skipped',
}

/** Worst first. */
export const STATUS_RANK: Record<Status, number> = {
  fail: 0,
  skipped: 1,
  warning: 2,
  bonus: 3,
  info: 4,
  pass: 5,
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
  style: 'Style',
}

export const SEVERITY_RANK: Record<Severity, number> = { critical: 0, major: 1, minor: 2, style: 3 }

export const CATEGORY_LABELS: Record<Category, string> = {
  structure: 'Structure',
  syntax: 'Compilation',
  functions: 'Required functions',
  explicit_tests: 'Known tests',
  derived_tests: 'Derived tests',
  heuristic_tests: 'Extra cases',
  output: 'Output matching',
  constraints: 'Constraints',
  runtime: 'Runtime',
  git: 'Git',
}

export const CATEGORY_ORDER: Category[] = [
  'structure',
  'syntax',
  'functions',
  'explicit_tests',
  'derived_tests',
  'output',
  'constraints',
  'runtime',
  'git',
  'heuristic_tests',
]

export interface ProvenanceMeta {
  label: string
  /** Sentence used in detail panels: "Source: Explicit requirement". */
  long: string
  tooltip: string
}

export const PROVENANCE_META: Record<Provenance, ProvenanceMeta> = {
  explicit: {
    label: 'Explicit',
    long: 'Explicit requirement',
    tooltip: 'Written literally in the subject',
  },
  derived: {
    label: 'Derived',
    long: 'Derived from a subject rule',
    tooltip: 'Deduced deterministically from an explicit rule of the subject',
  },
  heuristic: {
    label: 'Heuristic',
    long: 'Heuristic check',
    tooltip: 'Not an official requirement',
  },
  ai_extracted: {
    label: 'AI-extracted',
    long: 'AI-extracted requirement',
    tooltip: 'Needs review — not found verbatim in the subject',
  },
  user: {
    label: 'User',
    long: 'Added or edited by you',
    tooltip: 'Defined in the spec editor',
  },
}

export function compareChecks(a: CheckResult, b: CheckResult): number {
  const byStatus = STATUS_RANK[a.status] - STATUS_RANK[b.status]
  if (byStatus) return byStatus
  const sa = a.severity ? SEVERITY_RANK[a.severity] : 9
  const sb = b.severity ? SEVERITY_RANK[b.severity] : 9
  if (sa !== sb) return sa - sb
  return Number(b.mandatory) - Number(a.mandatory)
}

export interface CheckGroup {
  category: Category
  label: string
  checks: CheckResult[]
}

/** Groups checks by category (stable CATEGORY_ORDER), each group sorted worst first. */
export function groupChecksByCategory(checks: CheckResult[]): CheckGroup[] {
  const byCategory = new Map<Category, CheckResult[]>()
  for (const check of checks) {
    const list = byCategory.get(check.category) ?? []
    list.push(check)
    byCategory.set(check.category, list)
  }
  return CATEGORY_ORDER.filter((c) => byCategory.has(c)).map((category) => ({
    category,
    label: CATEGORY_LABELS[category],
    checks: [...(byCategory.get(category) ?? [])].sort(compareChecks),
  }))
}

export type CheckFilter = 'issues' | 'all' | 'warnings' | 'passed' | 'bonus'

export const CHECK_FILTERS: Array<{ value: CheckFilter; label: string; match: (c: CheckResult) => boolean }> = [
  { value: 'issues', label: 'To fix', match: (c) => c.status === 'fail' || c.status === 'skipped' },
  { value: 'warnings', label: 'Warnings', match: (c) => c.status === 'warning' || c.status === 'info' },
  { value: 'bonus', label: 'Bonus', match: (c) => c.bonus || c.status === 'bonus' },
  { value: 'passed', label: 'Passed', match: (c) => c.status === 'pass' },
  { value: 'all', label: 'All', match: () => true },
]
