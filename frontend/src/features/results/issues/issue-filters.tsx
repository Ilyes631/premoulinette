import { Search, X } from 'lucide-react'
import { Input } from '@/components/ui'
import { PROVENANCE_META, SEVERITY_LABELS } from '@/lib/check-meta'
import { cn } from '@/lib/cn'
import type { Provenance, Severity } from '@/lib/types'
import { STATUS_FILTERS, type IssueFilters, type StatusFilter } from '../shared/selectors'

const SEVERITIES: Severity[] = ['critical', 'major', 'minor', 'style']
const PROVENANCES: Provenance[] = ['explicit', 'derived', 'heuristic', 'ai_extracted', 'user']

const CHIP_TONE: Record<StatusFilter, string> = {
  fail: 'aria-pressed:border-fail/40 aria-pressed:bg-fail/10 aria-pressed:text-fail',
  warning: 'aria-pressed:border-warning/40 aria-pressed:bg-warning/10 aria-pressed:text-warning',
  bonus: 'aria-pressed:border-bonus/40 aria-pressed:bg-bonus/10 aria-pressed:text-bonus',
  info: 'aria-pressed:border-info/40 aria-pressed:bg-info/10 aria-pressed:text-info',
}

const selectClass =
  'h-9 rounded-lg border border-border-strong bg-bg-subtle px-2.5 text-sm text-fg transition-colors hover:bg-surface-2 focus-visible:border-accent'

interface IssueFiltersBarProps {
  filters: IssueFilters
  counts: Record<StatusFilter, number>
  onChange: (next: IssueFilters) => void
}

export function IssueFiltersBar({ filters, counts, onChange }: IssueFiltersBarProps) {
  const toggle = (value: StatusFilter) => {
    const has = filters.statuses.includes(value)
    onChange({ ...filters, statuses: has ? filters.statuses.filter((s) => s !== value) : [...filters.statuses, value] })
  }
  return (
    <div className="flex flex-col gap-2.5 lg:flex-row lg:items-center">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            aria-pressed={filters.statuses.includes(value)}
            onClick={() => toggle(value)}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 rounded-full border border-border-strong px-3 text-xs font-medium text-fg-muted transition-colors hover:text-fg',
              CHIP_TONE[value],
            )}
          >
            {label}
            <span className="tabular opacity-80">{counts[value]}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-1 flex-wrap gap-2 lg:justify-end">
        <label className="sr-only" htmlFor="issue-severity">
          Severity
        </label>
        <select
          id="issue-severity"
          className={selectClass}
          value={filters.severity}
          onChange={(e) => onChange({ ...filters, severity: e.target.value as IssueFilters['severity'] })}
        >
          <option value="all">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {SEVERITY_LABELS[s]}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="issue-provenance">
          Source
        </label>
        <select
          id="issue-provenance"
          className={selectClass}
          value={filters.provenance}
          onChange={(e) => onChange({ ...filters, provenance: e.target.value as IssueFilters['provenance'] })}
        >
          <option value="all">All sources</option>
          {PROVENANCES.map((p) => (
            <option key={p} value={p}>
              {PROVENANCE_META[p].label}
            </option>
          ))}
        </select>
        <div className="relative min-w-48 flex-1 lg:max-w-64">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
          <Input
            type="search"
            aria-label="Search issues"
            placeholder="Search issues, files, functions…"
            value={filters.query}
            onChange={(e) => onChange({ ...filters, query: e.target.value })}
            className="pr-8 pl-8"
          />
          {filters.query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => onChange({ ...filters, query: '' })}
              className="absolute top-1/2 right-1.5 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded text-fg-subtle hover:text-fg"
            >
              <X className="size-3.5" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
