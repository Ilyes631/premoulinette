import { ChevronRight, FileText, FolderGit2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card } from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatDateTime, formatPercent, formatRelativeTime, pluralize } from '@/lib/format'
import type { Verdict } from '@/lib/types'
import { formatDelta, type HistoryGroup } from './history-utils'
import { Sparkline } from './sparkline'

const VISIBLE_RUNS = 5

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  return verdict === 'ready' ? <Badge tone="pass">Ready</Badge> : <Badge tone="fail">Not ready</Badge>
}

export function DeltaText({ delta, className }: { delta: number | null; className?: string }) {
  const tone = delta === null || delta === 0 ? 'text-fg-subtle' : delta > 0 ? 'text-pass' : 'text-fail'
  return (
    <span className={cn('tabular text-xs', tone, className)} aria-label={delta === null ? 'first analysis' : `change ${formatDelta(delta)} points`}>
      {formatDelta(delta)}
    </span>
  )
}

export function HistoryGroupCard({ group }: { group: HistoryGroup }) {
  const [expanded, setExpanded] = useState(false)
  const newestFirst = [...group.runs].reverse()
  const shown = expanded ? newestFirst : newestFirst.slice(0, VISIBLE_RUNS)
  const latest = group.latest.item

  return (
    <Card className="overflow-hidden">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-border px-4 py-3.5 sm:px-5">
        <div className="min-w-0 flex-1">
          <h2 className="flex min-w-0 items-center gap-1.5 text-sm font-semibold text-fg">
            <FileText className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
            <span className="truncate">{group.subjectTitle}</span>
          </h2>
          <p className="mt-0.5 flex min-w-0 items-center gap-1.5 text-xs text-fg-muted">
            <FolderGit2 className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
            <span className="truncate">{group.projectName}</span>
            <span className="text-fg-subtle">· {pluralize(group.runs.length, 'analysis', 'analyses')}</span>
          </p>
        </div>
        <Sparkline values={group.runs.map((r) => r.item.readiness)} verdict={latest.verdict} />
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className={cn('tabular text-lg leading-none font-semibold', latest.verdict === 'ready' ? 'text-pass' : 'text-fg')}>
              {formatPercent(latest.readiness)}
            </div>
            <DeltaText delta={group.latest.delta} />
          </div>
          <VerdictChip verdict={latest.verdict} />
        </div>
      </header>
      <ol aria-label={`Analyses of ${group.projectName}`} className="divide-y divide-border">
        {shown.map(({ item, delta }) => (
          <li key={item.id}>
            <Link
              to={`/analyses/${item.id}`}
              className="group flex items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-surface-2 focus-visible:bg-surface-2 sm:px-5"
            >
              <span className="tabular w-10 shrink-0 text-xs text-fg-subtle">#{item.number}</span>
              <VerdictChip verdict={item.verdict} />
              <span className="tabular w-12 shrink-0 text-right font-medium text-fg">{formatPercent(item.readiness)}</span>
              <DeltaText delta={delta} className="w-16 shrink-0" />
              <span className="hidden min-w-0 flex-1 truncate text-xs text-fg-muted sm:inline">
                {item.mandatory_failures ? pluralize(item.mandatory_failures, 'mandatory failure') : 'No mandatory failure'}
                {item.bonus_completion !== null && ` · bonus ${formatPercent(item.bonus_completion)}`}
              </span>
              <time dateTime={item.created_at} title={formatDateTime(item.created_at)} className="ml-auto shrink-0 text-xs text-fg-subtle">
                {formatRelativeTime(item.created_at)}
              </time>
              <ChevronRight className="size-4 shrink-0 text-fg-subtle transition-transform group-hover:translate-x-0.5" aria-hidden />
            </Link>
          </li>
        ))}
      </ol>
      {group.runs.length > VISIBLE_RUNS && (
        <div className="border-t border-border px-4 py-2 sm:px-5">
          <Button size="sm" variant="ghost" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
            {expanded ? 'Show less' : `Show all ${group.runs.length} analyses`}
          </Button>
        </div>
      )}
    </Card>
  )
}
