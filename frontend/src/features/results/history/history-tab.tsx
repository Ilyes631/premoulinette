import { History, TrendingUp } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, EmptyState, Skeleton } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/cn'
import { formatDateTime, formatPercent, formatRelativeTime } from '@/lib/format'
import { useAnalyses } from '@/lib/queries'
import type { AnalysisListItem } from '@/lib/types'
import { useResults } from '../shared/results-context'
import { SectionCard } from '../shared/section-card'
import { chronological, previousAnalysis } from '../shared/selectors'
import { resultsPath } from '../shared/tabs'
import { formatDelta } from '../shared/meta'
import { ComparePanel } from './compare-panel'
import { Sparkline } from './sparkline'

export function HistoryTab() {
  const { report } = useResults()
  const analyses = useAnalyses({ subject_id: report.subject.id, project_id: report.project.id, limit: 50 })
  const items = useMemo(() => chronological(analyses.data ?? []), [analyses.data])
  const defaultBase = useMemo(() => previousAnalysis(items, report), [items, report])
  const [baseId, setBaseId] = useState<string | null>(null)
  const base = items.find((i) => i.id === baseId) ?? defaultBase

  if (analyses.isPending) {
    return (
      <div className="grid gap-4 lg:grid-cols-5" aria-busy aria-label="Loading history">
        <Skeleton className="h-72 rounded-xl lg:col-span-2" />
        <Skeleton className="h-72 rounded-xl lg:col-span-3" />
      </div>
    )
  }
  if (analyses.isError) {
    return (
      <EmptyState icon={History} tone="fail" title="Could not load the history" description={errorMessage(analyses.error)}>
        <Button variant="secondary" onClick={() => void analyses.refetch()}>
          Retry
        </Button>
      </EmptyState>
    )
  }

  const newestFirst = [...items].reverse()
  const currentIndex = items.findIndex((i) => i.id === report.id)
  const first = items[0]
  const last = items[items.length - 1]

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <SectionCard
        className="lg:col-span-2"
        icon={TrendingUp}
        title="Readiness over time"
        description={`${items.length} ${items.length === 1 ? 'analysis' : 'analyses'} of this project against this subject`}
        bodyClassName="px-2 sm:px-3"
      >
        {items.length > 0 && first && last && (
          <div className="mb-3 flex items-end justify-between gap-3 px-2">
            <Sparkline values={items.map((i) => i.readiness)} current={currentIndex} width={180} height={44} />
            {items.length > 1 && (
              <p className="text-right text-xs text-fg-muted">
                <span
                  className={cn(
                    'block text-sm font-semibold tabular',
                    last.readiness > first.readiness ? 'text-pass' : last.readiness < first.readiness ? 'text-fail' : 'text-fg',
                  )}
                >
                  {formatDelta(last.readiness - first.readiness)}
                </span>
                since #{first.number}
              </p>
            )}
          </div>
        )}
        <ol className="space-y-0.5">
          {newestFirst.map((item) => (
            <HistoryRow
              key={item.id}
              item={item}
              current={item.id === report.id}
              isBase={base?.id === item.id}
              canCompare={item.id !== report.id}
              onCompare={() => setBaseId(item.id)}
            />
          ))}
        </ol>
        {items.length <= 1 && (
          <p className="px-2 pt-3 text-xs text-fg-subtle">
            Re-analyze after fixing something to see your progress here (press <kbd className="font-mono">R</kbd>).
          </p>
        )}
      </SectionCard>
      <div className="lg:col-span-3">
        {base ? (
          <ComparePanel key={base.id} base={base} />
        ) : (
          <EmptyState
            icon={History}
            title="Nothing to compare yet"
            description="This is the first analysis of this project against this subject. The next one will show what you fixed."
            className="h-full"
          />
        )}
      </div>
    </div>
  )
}

function HistoryRow({
  item,
  current,
  isBase,
  canCompare,
  onCompare,
}: {
  item: AnalysisListItem
  current: boolean
  isBase: boolean
  canCompare: boolean
  onCompare: () => void
}) {
  return (
    <li
      className={cn(
        'flex items-center gap-2 rounded-lg px-2 py-2 text-sm',
        current && 'bg-surface-2',
        isBase && 'shadow-[inset_2px_0_0_var(--pm-accent)]',
      )}
    >
      <span
        className={cn('size-2 shrink-0 rounded-full', item.verdict === 'ready' ? 'bg-pass' : 'bg-fail')}
        aria-label={item.verdict === 'ready' ? 'Ready' : 'Not ready'}
        role="img"
      />
      <span className="min-w-0 flex-1 truncate">
        {current ? (
          <span className="font-medium text-fg">Analysis #{item.number}</span>
        ) : (
          <Link to={resultsPath(item.id)} className="font-medium text-fg hover:underline">
            Analysis #{item.number}
          </Link>
        )}
        <span className="text-fg-subtle"> · </span>
        <span className="font-medium text-fg tabular">{formatPercent(item.readiness, 1)}</span>
        <span className="text-fg-subtle"> · </span>
        <time className="text-fg-muted" dateTime={item.created_at} title={formatDateTime(item.created_at)}>
          {formatRelativeTime(item.created_at)}
        </time>
      </span>
      {current ? (
        <Badge tone="accent">Current</Badge>
      ) : canCompare ? (
        <Button size="sm" variant={isBase ? 'outline' : 'ghost'} aria-pressed={isBase} onClick={onCompare}>
          {isBase ? 'Comparing' : 'Compare'}
        </Button>
      ) : null}
    </li>
  )
}
