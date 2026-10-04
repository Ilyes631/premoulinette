import { FileQuestion, History, House, RotateCw, ServerCrash } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button, buttonVariants, EmptyState, Skeleton } from '@/components/ui'
import { ApiError, errorMessage } from '@/lib/api'

/** Page-shaped placeholder while the report loads (no layout shift when it arrives). */
export function ResultsSkeleton() {
  return (
    <div className="space-y-6" aria-busy aria-label="Loading analysis">
      <div className="flex flex-col gap-4 md:flex-row md:justify-between">
        <div className="space-y-2.5">
          <Skeleton className="h-3.5 w-48" />
          <Skeleton className="h-7 w-80 max-w-full" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-28" />
            <Skeleton className="h-6 w-36" />
          </div>
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-32" />
        </div>
      </div>
      <Skeleton className="h-[4.5rem] w-full rounded-xl" />
      <div className="flex gap-4 border-b border-border pb-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-5 w-16" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-52 rounded-xl lg:col-span-2" />
        <div className="grid gap-3">
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
        <Skeleton className="h-64 rounded-xl lg:col-span-2" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  )
}

export function ResultsError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const notFound = error instanceof ApiError && error.status === 404
  if (notFound) {
    return (
      <EmptyState
        icon={FileQuestion}
        title="Analysis not found"
        description="This analysis does not exist (anymore). It may have been run with another data folder."
      >
        <Link to="/history" className={buttonVariants({ variant: 'secondary' })}>
          <History aria-hidden /> All analyses
        </Link>
        <Link to="/" className={buttonVariants({ variant: 'primary' })}>
          <House aria-hidden /> New analysis
        </Link>
      </EmptyState>
    )
  }
  return (
    <EmptyState icon={ServerCrash} tone="fail" title="Could not load this analysis" description={errorMessage(error)}>
      <Button variant="secondary" onClick={onRetry}>
        <RotateCw aria-hidden /> Retry
      </Button>
    </EmptyState>
  )
}
