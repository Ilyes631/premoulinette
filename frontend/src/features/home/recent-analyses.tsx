import { ArrowRight, ChevronRight, CircleCheck, CircleX, History, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge, Button, Skeleton } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/cn'
import { formatDateTime, formatPercent, formatRelativeTime } from '@/lib/format'
import { useAnalyses } from '@/lib/queries'
import type { AnalysisListItem } from '@/lib/types'

export function RecentAnalyses() {
  const analyses = useAnalyses({ limit: 5 })

  return (
    <section aria-labelledby="recent-analyses-title" className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 id="recent-analyses-title" className="text-sm font-semibold text-fg">
            Recent analyses
          </h2>
          <p className="text-xs text-fg-subtle">Your last runs on this machine.</p>
        </div>
        <Link
          to="/history"
          className="group inline-flex items-center gap-1 rounded-sm text-xs font-medium text-fg-muted hover:text-fg"
        >
          View all
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        {analyses.isPending ? (
          <ul aria-busy="true" aria-label="Loading recent analyses" className="divide-y divide-border">
            {Array.from({ length: 3 }, (_, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-3">
                <Skeleton className="h-4 w-8" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-5 w-16" />
              </li>
            ))}
          </ul>
        ) : analyses.isError ? (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm">
            <p className="text-fg-muted">
              <span className="font-medium text-fail">Could not load analyses.</span> {errorMessage(analyses.error)}
            </p>
            <Button size="sm" variant="secondary" onClick={() => void analyses.refetch()}>
              <RefreshCw aria-hidden />
              Retry
            </Button>
          </div>
        ) : analyses.data.length === 0 ? (
          <div className="flex items-center gap-3 px-4 py-6 text-sm text-fg-muted">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border-strong bg-surface-2">
              <History className="size-4" aria-hidden />
            </div>
            <p>No analyses yet. Import a subject and a project above, then press Analyze.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {analyses.data.slice(0, 5).map((item) => (
              <RecentRow key={item.id} item={item} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function RecentRow({ item }: { item: AnalysisListItem }) {
  const ready = item.verdict === 'ready'
  const readiness = item.readiness ?? item.mandatory_readiness
  return (
    <li>
      <Link
        to={`/analyses/${encodeURIComponent(item.id)}`}
        className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-2/60 focus-visible:bg-surface-2/60"
      >
        <span className="tabular w-9 shrink-0 font-mono text-xs text-fg-subtle">#{item.number}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">{item.subject_title}</span>
          <span className="block truncate text-xs text-fg-muted">
            {item.project_name}
            <span aria-hidden> · </span>
            <time dateTime={item.created_at} title={formatDateTime(item.created_at)}>
              {formatRelativeTime(item.created_at)}
            </time>
          </span>
        </span>
        <span
          className={cn(
            'tabular hidden w-12 shrink-0 text-right text-sm font-semibold min-[420px]:block',
            ready ? 'text-pass' : readiness >= 70 ? 'text-warning' : 'text-fail',
          )}
          aria-label={`Readiness ${formatPercent(readiness)}`}
        >
          {formatPercent(readiness)}
        </span>
        <Badge tone={ready ? 'pass' : 'fail'} size="md" className="shrink-0">
          {ready ? <CircleCheck aria-hidden /> : <CircleX aria-hidden />}
          {ready ? 'Ready' : 'Not ready'}
        </Badge>
        <ChevronRight
          className="size-4 shrink-0 text-fg-subtle transition-transform group-hover:translate-x-0.5"
          aria-hidden
        />
      </Link>
    </li>
  )
}
