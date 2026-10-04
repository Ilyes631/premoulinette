import { History, RotateCw, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, buttonVariants, EmptyState, Input, Skeleton, Stat } from '@/components/ui'
import { HistoryGroupCard } from '@/features/history/history-group-card'
import { groupAnalyses, matchesQuery } from '@/features/history/history-utils'
import { errorMessage } from '@/lib/api'
import { useAnalyses } from '@/lib/queries'

const HISTORY_LIMIT = 100

export function HistoryPage() {
  const query = useAnalyses({ limit: HISTORY_LIMIT })
  const [search, setSearch] = useState('')
  const deferred = useDeferredValue(search)
  const groups = useMemo(() => groupAnalyses(query.data ?? []), [query.data])
  const visible = groups.filter((g) => matchesQuery(g, deferred))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">History</h1>
          <p className="mt-1 text-sm text-fg-muted">Every analysis, grouped by subject and project, with the readiness trend.</p>
        </div>
        {groups.length > 0 && (
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-fg-subtle" aria-hidden />
            <Input
              type="search"
              aria-label="Filter by subject or project"
              placeholder="Filter by subject or project…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>
        )}
      </div>

      {query.isPending ? (
        <div className="space-y-3" aria-busy aria-label="Loading the history">
          <Skeleton className="h-20" />
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
        </div>
      ) : query.isError ? (
        <EmptyState icon={History} tone="fail" title="The history could not be loaded" description={errorMessage(query.error)}>
          <Button onClick={() => void query.refetch()}>
            <RotateCw aria-hidden /> Retry
          </Button>
        </EmptyState>
      ) : groups.length === 0 ? (
        <EmptyState
          icon={History}
          title="No analysis yet"
          description="Import a subject and your project, then run an analysis: every run is kept here so you can follow your progress."
        >
          <Link to="/" className={buttonVariants({ variant: 'primary' })}>
            Start an analysis
          </Link>
        </EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Analyses" value={query.data.length} hint={query.data.length >= HISTORY_LIMIT ? `latest ${HISTORY_LIMIT}` : undefined} />
            <Stat label="Subject × project" value={groups.length} />
            <Stat label="Ready now" tone="pass" value={groups.filter((g) => g.latest.item.verdict === 'ready').length} hint="latest run is ready" />
            <Stat label="Not ready" tone="fail" value={groups.filter((g) => g.latest.item.verdict !== 'ready').length} hint="latest run" />
          </div>
          {visible.length === 0 ? (
            <EmptyState icon={Search} title="No match" description={`Nothing matches “${deferred.trim()}”.`}>
              <Button variant="ghost" onClick={() => setSearch('')}>
                Clear filter
              </Button>
            </EmptyState>
          ) : (
            <div className="space-y-4">
              {visible.map((group) => (
                <HistoryGroupCard key={group.key} group={group} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
