import { CircleCheckBig, SearchX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Button, EmptyState, Kbd } from '@/components/ui'
import { useResults } from '../shared/results-context'
import {
  DEFAULT_ISSUE_FILTERS,
  groupIssuesByFile,
  matchesIssueFilters,
  statusFilterOf,
  type IssueFilters,
  type StatusFilter,
} from '../shared/selectors'
import { FileGroupSection } from './file-group'
import { IssueFiltersBar } from './issue-filters'

export function IssuesTab() {
  const { report, openCheck } = useResults()
  const [searchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') ?? ''
  const selectedId = searchParams.get('check')
  const [filters, setFilters] = useState<IssueFilters>(() => ({ ...DEFAULT_ISSUE_FILTERS, query: initialQuery }))
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set())

  const counts = useMemo(() => {
    const out: Record<StatusFilter, number> = { fail: 0, warning: 0, bonus: 0, info: 0 }
    for (const check of report.checks) {
      const bucket = statusFilterOf(check.status)
      if (bucket) out[bucket] += 1
    }
    return out
  }, [report.checks])

  const groups = useMemo(() => {
    const filtered = report.checks.filter((c) => matchesIssueFilters(c, filters))
    return groupIssuesByFile(filtered, report.score.files, report.project.detected_root)
  }, [filters, report.checks, report.project.detected_root, report.score.files])

  const visibleIds = useMemo(
    () => groups.filter((g) => !collapsed.has(g.key)).flatMap((g) => g.checks.map((c) => c.id)),
    [collapsed, groups],
  )
  const shown = groups.reduce((n, g) => n + g.checks.length, 0)
  const anyIssue = counts.fail + counts.warning + counts.bonus > 0
  const filtersActive =
    filters.query !== '' ||
    filters.severity !== 'all' ||
    filters.provenance !== 'all' ||
    filters.statuses.join() !== DEFAULT_ISSUE_FILTERS.statuses.join()

  const toggleGroup = (key: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  return (
    <div className="space-y-4">
      <IssueFiltersBar filters={filters} counts={counts} onChange={setFilters} />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-fg-muted">
        <p aria-live="polite">
          <span className="font-medium text-fg tabular">{shown}</span> {shown === 1 ? 'issue' : 'issues'} in{' '}
          <span className="font-medium text-fg tabular">{groups.length}</span> {groups.length === 1 ? 'group' : 'groups'}
          {filtersActive && (
            <Button variant="link" size="sm" className="ml-2 text-xs" onClick={() => setFilters(DEFAULT_ISSUE_FILTERS)}>
              Reset filters
            </Button>
          )}
        </p>
        <p className="hidden items-center gap-1.5 sm:flex">
          <Kbd>J</Kbd>
          <Kbd>K</Kbd> move <span className="text-fg-subtle">·</span> <Kbd>Enter</Kbd> open <span className="text-fg-subtle">·</span>{' '}
          <Kbd>Esc</Kbd> close
        </p>
      </div>

      {!anyIssue && counts.info === 0 ? (
        <EmptyState
          icon={CircleCheckBig}
          title="No issues"
          description="Every check that could be verified from the subject passed. Hidden grader tests may still exist."
        />
      ) : groups.length === 0 ? (
        <EmptyState icon={SearchX} title="No issue matches these filters" description="Try another status, severity or search.">
          <Button variant="secondary" onClick={() => setFilters(DEFAULT_ISSUE_FILTERS)}>
            Reset filters
          </Button>
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => (
            <FileGroupSection
              key={group.key}
              group={group}
              expanded={!collapsed.has(group.key)}
              onToggle={() => toggleGroup(group.key)}
              selectedId={selectedId}
              onSelect={(check) => openCheck(check.id, visibleIds)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
