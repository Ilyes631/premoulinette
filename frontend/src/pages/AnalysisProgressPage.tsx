import { ArrowLeft, CircleX, FileQuestion, History, RotateCcw, Settings, Timer, WifiOff } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useMemo, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button, buttonVariants, EmptyState, ProgressBar, Skeleton, Spinner } from '@/components/ui'
import { readSelection } from '@/features/home/selection'
import { recallJob, rememberJob, type JobContext } from '@/features/progress/job-context'
import { StageStepper } from '@/features/progress/stage-stepper'
import { useElapsed } from '@/features/progress/use-elapsed'
import { errorMessage, isApiError } from '@/lib/api'
import { cn } from '@/lib/cn'
import { formatElapsed, toPercent } from '@/lib/format'
import { isJobFinished, useJob, useStartAnalysis } from '@/lib/queries'
import type { JobState } from '@/lib/types'

const SETTINGS_HINT = /docker|developer mode|sandbox|settings/i

export function AnalysisProgressPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const job = useJob(id)
  const context = useMemo(() => recallJob(id), [id])
  const data = job.data
  const finished = isJobFinished(data)
  const elapsed = useElapsed(data?.created_at, data?.finished_at, Boolean(data) && !finished)
  const percent = toPercent(data?.progress)

  // Done: open the report (replace, so "back" does not land on a finished job).
  useEffect(() => {
    if (data?.status === 'done' && data.result_id) {
      navigate(`/analyses/${encodeURIComponent(data.result_id)}`, { replace: true })
    }
  }, [data?.status, data?.result_id, navigate])

  useEffect(() => {
    const previous = document.title
    if (data && !finished) document.title = `${Math.floor(percent)}% · Analyzing — PréMoulinette`
    else if (data?.status === 'error') document.title = 'Analysis failed — PréMoulinette'
    return () => {
      document.title = previous
    }
  }, [data, finished, percent])

  if (!id) return <JobNotFound />

  if (job.isPending) {
    return (
      <ProgressFrame>
        <div className="flex flex-col gap-5" aria-busy="true" aria-label="Loading analysis">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-2 w-full" />
          {Array.from({ length: 7 }, (_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="size-6 rounded-full" />
              <Skeleton className="h-4 flex-1" />
            </div>
          ))}
        </div>
      </ProgressFrame>
    )
  }

  if (!data) {
    if (isApiError(job.error) && job.error.status === 404) return <JobNotFound />
    return (
      <ProgressFrame>
        <EmptyState
          icon={WifiOff}
          tone="fail"
          title="Cannot load this analysis"
          description={errorMessage(job.error)}
          className="border-none py-6"
        >
          <Button variant="primary" onClick={() => void job.refetch()}>
            <RotateCcw aria-hidden />
            Retry
          </Button>
          <Link to="/" className={buttonVariants({ variant: 'ghost' })}>
            Back home
          </Link>
        </EmptyState>
      </ProgressFrame>
    )
  }

  if (data.status === 'error' || (data.status === 'done' && !data.result_id)) {
    return <JobFailed job={data} context={context} />
  }

  const current = data.stages.find((s) => s.status === 'running')
  const doneCount = data.stages.filter((s) => s.status === 'done').length
  const opening = data.status === 'done'

  return (
    <ProgressFrame>
      <JobHeader
        title={opening ? 'Analysis complete' : 'Analyzing your project'}
        context={context}
        elapsed={elapsed}
        busy={!opening}
      />

      <div className="mt-6 flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3 text-xs">
          <span className="truncate text-fg-muted" aria-live="polite">
            {opening
              ? 'Opening the report…'
              : data.status === 'queued'
                ? 'Queued — waiting for a worker…'
                : (current?.label ?? 'Starting…')}
          </span>
          <span className="tabular shrink-0 font-mono font-medium text-fg">{Math.floor(percent)}%</span>
        </div>
        <ProgressBar value={percent} label="Analysis progress" tone={opening ? 'pass' : 'accent'} size="sm" />
        <p className="tabular text-2xs text-fg-subtle">
          {doneCount} of {data.stages.length} stages
        </p>
      </div>

      <div className="mt-6 border-t border-border pt-5">
        <StageStepper stages={data.stages} />
      </div>

      {job.isError && (
        <p role="status" className="mt-5 flex items-center gap-2 text-xs text-warning">
          <WifiOff className="size-3.5" aria-hidden />
          Connection to the server lost — retrying…
        </p>
      )}

      <p className="mt-6 border-t border-border pt-4 text-xs text-fg-subtle">
        Student code runs only inside the sandbox. You can leave this page: the report will appear in History.
      </p>
    </ProgressFrame>
  )
}

function ProgressFrame({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-center py-2 sm:py-8">
      <motion.div
        initial={{ opacity: 0, y: 8, scale: 0.99 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.28, ease: [0.25, 1, 0.5, 1] }}
        className="w-full max-w-xl rounded-2xl border border-border bg-surface p-5 shadow-card sm:p-7"
      >
        {children}
      </motion.div>
    </div>
  )
}

function JobHeader({
  title,
  context,
  elapsed,
  busy,
  failed = false,
}: {
  title: string
  context: JobContext | null
  elapsed: number
  busy: boolean
  failed?: boolean
}) {
  const names = [context?.subject_title, context?.project_name].filter(Boolean) as string[]
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-2xs font-medium tracking-wider text-fg-subtle uppercase">
          {busy && <Spinner className="size-3 text-accent-fg" label="Running" />}
          {failed && <CircleX className="size-3 text-fail" aria-hidden />}
          Analysis
        </p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-fg">{title}</h1>
        {names.length > 0 && (
          <p className="mt-1 truncate text-sm text-fg-muted" title={names.join(' · ')}>
            {names.join(' · ')}
          </p>
        )}
      </div>
      <div
        className="flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-surface-2 px-2 py-1 text-fg-muted"
        aria-label={`Elapsed time ${formatElapsed(elapsed)}`}
        role="timer"
      >
        <Timer className="size-3.5" aria-hidden />
        <span className="tabular font-mono text-xs">{formatElapsed(elapsed)}</span>
      </div>
    </div>
  )
}

function JobFailed({ job, context }: { job: JobState; context: JobContext | null }) {
  const navigate = useNavigate()
  const start = useStartAnalysis()
  const elapsed = useElapsed(job.created_at, job.finished_at, false)
  const message =
    job.error?.trim() ||
    (job.status === 'done' ? 'The analysis finished but no report was produced.' : 'The analysis failed for an unknown reason.')
  const retryIds = useMemo<JobContext | null>(() => {
    if (context) return context
    const selection = readSelection()
    return selection.subjectId && selection.projectId
      ? { subject_id: selection.subjectId, project_id: selection.projectId }
      : null
  }, [context])

  const retry = () => {
    if (!retryIds) return
    start.mutate(
      { subject_id: retryIds.subject_id, project_id: retryIds.project_id },
      {
        onSuccess: ({ job_id }) => {
          rememberJob(job_id, retryIds)
          navigate(`/jobs/${encodeURIComponent(job_id)}`, { replace: true })
        },
      },
    )
  }

  return (
    <ProgressFrame>
      <JobHeader title="Analysis failed" context={context} elapsed={elapsed} busy={false} failed />

      <div role="alert" className="mt-5 rounded-xl border border-fail/30 bg-fail/[0.06] p-4">
        <p className="text-sm font-medium text-fail">The analysis could not complete</p>
        <p className="mt-1 text-sm break-words whitespace-pre-wrap text-fg">{message}</p>
      </div>

      {start.isError && (
        <p role="alert" className="mt-3 text-xs text-fail">
          Retry failed: {errorMessage(start.error)}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {retryIds && (
          <Button variant="primary" onClick={retry} loading={start.isPending}>
            {!start.isPending && <RotateCcw aria-hidden />}
            Retry analysis
          </Button>
        )}
        {SETTINGS_HINT.test(message) && (
          <Link to="/settings" className={buttonVariants({ variant: 'secondary' })}>
            <Settings aria-hidden />
            Open settings
          </Link>
        )}
        <Link to="/" className={buttonVariants({ variant: 'ghost' })}>
          <ArrowLeft aria-hidden />
          Back home
        </Link>
      </div>

      {job.stages.length > 0 && (
        <div className={cn('mt-6 border-t border-border pt-5')}>
          <StageStepper stages={job.stages} />
        </div>
      )}
    </ProgressFrame>
  )
}

function JobNotFound() {
  return (
    <ProgressFrame>
      <EmptyState
        icon={FileQuestion}
        title="Analysis job not found"
        description="Jobs are kept in memory by the local server: this one may have been cleared by a restart. Finished analyses stay in History."
        className="border-none py-6"
      >
        <Link to="/" className={buttonVariants({ variant: 'primary' })}>
          <ArrowLeft aria-hidden />
          Back home
        </Link>
        <Link to="/history" className={buttonVariants({ variant: 'secondary' })}>
          <History aria-hidden />
          History
        </Link>
      </EmptyState>
    </ProgressFrame>
  )
}
