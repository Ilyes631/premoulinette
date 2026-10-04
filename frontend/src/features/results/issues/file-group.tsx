import { ChevronRight, FileCode2, FolderTree } from 'lucide-react'
import { useId } from 'react'
import { CheckRow } from '@/components/results'
import { SeverityBadge } from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatPercent } from '@/lib/format'
import type { CheckResult, Severity } from '@/lib/types'
import type { FileGroup } from '../shared/selectors'

function worstSeverity(checks: CheckResult[]): Severity | null {
  const order: Severity[] = ['critical', 'major', 'minor', 'style']
  for (const s of order) if (checks.some((c) => c.severity === s && c.status !== 'pass')) return s
  return null
}

function dirOf(path: string): string {
  const i = path.lastIndexOf('/')
  return i > 0 ? path.slice(0, i + 1) : ''
}

interface FileGroupSectionProps {
  group: FileGroup
  expanded: boolean
  onToggle: () => void
  selectedId: string | null
  onSelect: (check: CheckResult) => void
}

/** Collapsible group of issues of one file: "launch_sequence.py 92% · 2 issues". */
export function FileGroupSection({ group, expanded, onToggle, selectedId, onSelect }: FileGroupSectionProps) {
  const panelId = useId()
  const severity = worstSeverity(group.checks)
  const count = group.checks.length
  const Icon = group.file ? FileCode2 : FolderTree
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card" data-file-group={group.key}>
      <h3>
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={onToggle}
          className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface-2/60 sm:px-4"
        >
          <ChevronRight
            className={cn('size-4 shrink-0 text-fg-subtle transition-transform duration-150', expanded && 'rotate-90')}
            aria-hidden
          />
          <Icon className="size-4 shrink-0 text-fg-muted" aria-hidden />
          <span className="flex min-w-0 flex-1 items-baseline gap-2">
            <span className="min-w-0 truncate font-mono text-sm">
              {group.file && <span className="text-fg-subtle">{dirOf(group.file)}</span>}
              <span className="font-medium text-fg">{group.label}</span>
            </span>
            {group.score && group.score.score !== null && (
              <span className="shrink-0 text-xs font-medium text-fg-muted tabular">{formatPercent(group.score.score)}</span>
            )}
            <span className="shrink-0 text-xs text-fg-subtle">
              · {count} {count === 1 ? 'issue' : 'issues'}
            </span>
          </span>
          {severity && <SeverityBadge severity={severity} className="hidden sm:inline-flex" />}
        </button>
      </h3>
      {expanded && (
        <ul id={panelId} className="divide-y divide-border border-t border-border px-1 py-1 sm:px-2">
          {group.checks.map((check) => (
            <li key={check.id} data-nav-row>
              <CheckRow check={check} selected={selectedId === check.id} onSelect={onSelect} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
