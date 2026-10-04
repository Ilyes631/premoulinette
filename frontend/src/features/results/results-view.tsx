import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui'
import { compareChecks } from '@/lib/check-meta'
import type { AnalysisReport, CheckResult, Location } from '@/lib/types'
import { FilesTab } from './files/files-tab'
import { HistoryTab } from './history/history-tab'
import { IssuesTab } from './issues/issues-tab'
import { OverviewTab } from './overview/overview-tab'
import { ReportTab } from './report/report-tab'
import { CheckDetailSheet } from './shared/check-detail-sheet'
import { CodeViewerDialog } from './shared/code-viewer-dialog'
import { ResultsContext, type FileTarget, type ResultsContextValue } from './shared/results-context'
import { ResultsHeader } from './shared/results-header'
import { isIssue, isMandatoryFailure, isTestCheck } from './shared/selectors'
import { RESULT_TAB_LABELS, RESULT_TABS, resultsPath, type ResultTab } from './shared/tabs'
import { VerdictBanner } from './shared/verdict-banner'
import { TestsTab } from './tests/tests-tab'
import { useReanalyzeAction } from './shared/use-reanalyze-action'

export const CHECK_PARAM = 'check'

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

function focusTarget(row: HTMLElement): HTMLElement {
  if (row instanceof HTMLButtonElement || row instanceof HTMLAnchorElement) return row
  return row.querySelector<HTMLElement>('button, a[href]') ?? row
}

interface ResultsViewProps {
  report: AnalysisReport
  tab: ResultTab
}

/** The readiness dashboard of one analysis: header, verdict, tabs, check detail sheet, code viewer. */
export function ResultsView({ report, tab }: ResultsViewProps) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [codeTarget, setCodeTarget] = useState<FileTarget | null>(null)
  const panelsRef = useRef<HTMLDivElement>(null)
  const reanalyze = useReanalyzeAction(report)

  const checksById = useMemo(() => new Map(report.checks.map((c) => [c.id, c])), [report.checks])
  const issues = useMemo(() => report.checks.filter(isIssue).sort(compareChecks), [report.checks])
  const defaultNav = useMemo(() => issues.map((c) => c.id), [issues])
  const [navList, setNavList] = useState<string[]>(defaultNav)
  const testCount = useMemo(() => report.checks.filter(isTestCheck).length, [report.checks])
  const criticalFailures = useMemo(
    () => report.checks.filter((c) => isMandatoryFailure(c) && c.severity === 'critical').length,
    [report.checks],
  )

  const selectedId = searchParams.get(CHECK_PARAM)
  const selected: CheckResult | null = (selectedId && checksById.get(selectedId)) || null

  const setSelected = useCallback(
    (checkId: string | null) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (checkId) next.set(CHECK_PARAM, checkId)
          else next.delete(CHECK_PARAM)
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const openCheck = useCallback(
    (checkId: string, list?: string[]) => {
      setNavList(list && list.length ? list : defaultNav)
      setSelected(checkId)
    },
    [defaultNav, setSelected],
  )

  const goToTab = useCallback(
    (next: ResultTab, search?: Record<string, string>) => {
      const qs = search ? new URLSearchParams(search).toString() : ''
      navigate({ pathname: resultsPath(report.id, next), search: qs ? `?${qs}` : '' })
    },
    [navigate, report.id],
  )

  const openFile = useCallback((target: FileTarget) => setCodeTarget(target), [])
  const openLocation = useCallback((loc: Location) => setCodeTarget({ file: loc.file, line: loc.line }), [])

  const context = useMemo<ResultsContextValue>(
    () => ({ report, openCheck, openFile, goToTab }),
    [report, openCheck, openFile, goToTab],
  )

  useEffect(() => {
    const previous = document.title
    const verdict = report.score.verdict === 'ready' ? 'Ready' : 'Not ready'
    document.title = `${verdict} · ${report.subject.title} — PréMoulinette`
    return () => {
      document.title = previous
    }
  }, [report.score.verdict, report.subject.title])

  // Keyboard: j/k move between issues (or between checks while the sheet is open), R re-analyzes.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return
      if (isEditableTarget(event.target) || codeTarget) return
      const key = event.key.toLowerCase()
      if (key === 'j' || key === 'k') {
        const delta = key === 'j' ? 1 : -1
        if (selected) {
          const index = navList.indexOf(selected.id)
          const nextId = index >= 0 ? navList[index + delta] : undefined
          if (nextId) setSelected(nextId)
          event.preventDefault()
          return
        }
        const rows = Array.from(panelsRef.current?.querySelectorAll<HTMLElement>('[data-nav-row]') ?? [])
        if (rows.length === 0) return
        const current = rows.findIndex((row) => row.contains(document.activeElement))
        const nextIndex =
          current === -1 ? (delta > 0 ? 0 : rows.length - 1) : Math.min(rows.length - 1, Math.max(0, current + delta))
        const target = focusTarget(rows[nextIndex] as HTMLElement)
        target.focus()
        target.scrollIntoView?.({ block: 'nearest' })
        event.preventDefault()
      } else if (key === 'r' && !event.shiftKey) {
        if (selected || document.querySelector('[role="dialog"], [role="menu"]')) return
        event.preventDefault()
        reanalyze.run()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [codeTarget, navList, reanalyze, selected, setSelected])

  const counts: Partial<Record<ResultTab, number>> = { issues: issues.length, tests: testCount }

  return (
    <ResultsContext.Provider value={context}>
      <div className="space-y-6">
        <ResultsHeader report={report} onReanalyze={reanalyze.run} reanalyzing={reanalyze.isPending} />
        <VerdictBanner
          score={report.score}
          criticalFailures={criticalFailures}
          primaryLabel={report.score.verdict === 'ready' ? 'View report' : 'Review issues'}
          onPrimary={() => goToTab(report.score.verdict === 'ready' ? 'report' : 'issues')}
        />
        <Tabs value={tab} onValueChange={(value) => goToTab(value as ResultTab)} activationMode="manual">
          <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <TabsList variant="underline" aria-label="Analysis sections" className="min-w-max">
              {RESULT_TABS.map((t) => (
                <TabsTrigger key={t} value={t}>
                  {RESULT_TAB_LABELS[t]}
                  {counts[t] !== undefined && (
                    <span className="rounded-full bg-surface-3 px-1.5 py-px text-2xs font-medium text-fg-muted tabular">
                      {counts[t]}
                    </span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          <div ref={panelsRef} className="pt-6">
            <TabsContent value="overview">
              <OverviewTab />
            </TabsContent>
            <TabsContent value="issues">
              <IssuesTab />
            </TabsContent>
            <TabsContent value="tests">
              <TestsTab />
            </TabsContent>
            <TabsContent value="files">
              <FilesTab />
            </TabsContent>
            <TabsContent value="report">
              <ReportTab />
            </TabsContent>
            <TabsContent value="history">
              <HistoryTab />
            </TabsContent>
          </div>
        </Tabs>
      </div>

      <CheckDetailSheet
        analysisId={report.id}
        check={selected}
        checksById={checksById}
        navList={navList}
        onNavigate={setSelected}
        onClose={() => setSelected(null)}
        onOpenFile={openLocation}
      />
      <CodeViewerDialog
        projectId={report.project.id}
        projectPath={report.project.path}
        target={codeTarget}
        onClose={() => setCodeTarget(null)}
      />
    </ResultsContext.Provider>
  )
}
