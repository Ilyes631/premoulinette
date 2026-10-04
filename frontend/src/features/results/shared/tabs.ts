/** Results dashboard tabs: each one is addressable as /analyses/:id/:tab. */
export const RESULT_TABS = ['overview', 'issues', 'tests', 'files', 'report', 'history'] as const

export type ResultTab = (typeof RESULT_TABS)[number]

export const DEFAULT_RESULT_TAB: ResultTab = 'overview'

export const RESULT_TAB_LABELS: Record<ResultTab, string> = {
  overview: 'Overview',
  issues: 'Issues',
  tests: 'Tests',
  files: 'Files',
  report: 'Report',
  history: 'History',
}

export function isResultTab(value: string | null | undefined): value is ResultTab {
  return typeof value === 'string' && (RESULT_TABS as readonly string[]).includes(value)
}

export function resultsPath(analysisId: string, tab: ResultTab = DEFAULT_RESULT_TAB): string {
  return `/analyses/${encodeURIComponent(analysisId)}/${tab}`
}
