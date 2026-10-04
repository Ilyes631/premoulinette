import { createContext, useContext } from 'react'
import type { AnalysisReport } from '@/lib/types'
import type { ResultTab } from './tabs'

export interface FileTarget {
  file: string
  line: number | null
}

export interface ResultsContextValue {
  report: AnalysisReport
  /**
   * Opens the detail sheet of a check. `navList` is the ordered list of check ids the user is browsing
   * (used by j/k and the prev/next buttons of the sheet).
   */
  openCheck: (checkId: string, navList?: string[]) => void
  /** Opens the read-only code viewer at a file (and line). */
  openFile: (target: FileTarget) => void
  /** Switches tab, optionally with search params (e.g. `{ q: 'kelvin.py' }`). */
  goToTab: (tab: ResultTab, search?: Record<string, string>) => void
}

export const ResultsContext = createContext<ResultsContextValue | null>(null)

export function useResults(): ResultsContextValue {
  const value = useContext(ResultsContext)
  if (!value) throw new Error('useResults() must be used inside <ResultsView>')
  return value
}
