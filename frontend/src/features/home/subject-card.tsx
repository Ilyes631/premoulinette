import { ArrowRight, CircleAlert, CircleCheck, FileText, RefreshCw, ScrollText, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { DemoReadOnlyNotice } from '@/components/demo/read-only-notice'
import { Badge, Button, DropZone, ProgressBar, Skeleton, Spinner, Tooltip } from '@/components/ui'
import { errorMessage, isApiError, isDemoReadOnlyError } from '@/lib/api'
import { cn } from '@/lib/cn'
import { useSubject, useUploadSubject } from '@/lib/queries'
import type { SubjectMediaType, SubjectView } from '@/lib/types'
import { isSubjectFile, SUBJECT_ACCEPT } from '@/lib/uploads'
import { DropArea } from './drop-area'
import { ImportCard, ImportError, type ImportState } from './import-card'

const MEDIA_LABEL: Record<SubjectMediaType, string> = {
  html: 'HTML',
  markdown: 'Markdown',
  text: 'Text',
  pdf: 'PDF',
}

export interface SubjectCardProps {
  subjectId: string | null
  onSelect: (id: string | null) => void
  /** Another action (demo loading) is filling this card. */
  externalBusy?: boolean
  onStateChange?: (state: ImportState) => void
}

export function SubjectCard({ subjectId, onSelect, externalBusy = false, onStateChange }: SubjectCardProps) {
  const subject = useSubject(subjectId)
  const upload = useUploadSubject()
  const [pendingName, setPendingName] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  // A remembered id that no longer exists on the server (data dir wiped): forget it.
  useEffect(() => {
    if (subject.isError && isApiError(subject.error) && subject.error.status === 404) onSelect(null)
  }, [subject.isError, subject.error, onSelect])

  const handleFiles = (files: File[]) => {
    const file = files[0]
    if (!file) return
    if (!isSubjectFile(file)) {
      setLocalError(`"${file.name}" is not a supported subject. Use .html, .htm, .md, .markdown, .txt or .pdf.`)
      return
    }
    setLocalError(null)
    setPendingName(file.name)
    upload.mutate(file, {
      onSuccess: (view) => onSelect(view.id),
      onSettled: () => setPendingName(null),
    })
  }

  const uploading = upload.isPending || externalBusy
  const data = subject.data && subject.data.id === subjectId ? subject.data : undefined
  const loading = Boolean(subjectId) && subject.isPending
  // The online demo refuses uploads: explained by a notice, not reported as a failure.
  const demoRefusal = !localError && isDemoReadOnlyError(upload.error) ? upload.error : null
  const state: ImportState = uploading
    ? 'uploading'
    : (upload.isError && !demoRefusal) || localError || (subject.isError && !data)
      ? 'error'
      : data
        ? 'ready'
        : loading
          ? 'loading'
          : 'empty'

  useEffect(() => {
    onStateChange?.(state)
  }, [state, onStateChange])

  const errorText = localError ?? (upload.isError ? errorMessage(upload.error) : null)

  return (
    <ImportCard
      step={1}
      labelId="subject-card-title"
      title="Subject"
      description="The assignment statement: we extract its exact contract."
      icon={ScrollText}
      state={state}
    >
      {data && !uploading ? (
        <SubjectSummary subject={data} onFiles={handleFiles} />
      ) : loading && !uploading ? (
        <SubjectSkeleton />
      ) : (
        <DropArea
          onFiles={handleFiles}
          accept={SUBJECT_ACCEPT}
          inputLabel="Subject file"
          icon={FileText}
          title="Drop subject.html / PDF / Markdown here or browse"
          hint="Accepted: .html .htm .md .markdown .txt .pdf"
          browseLabel="Browse files"
          busy={
            uploading ? (
              <BusyContent
                title={pendingName ? `Parsing ${pendingName}…` : 'Loading the demo subject…'}
                hint="Extracting files, signatures, examples and constraints"
              />
            ) : undefined
          }
        />
      )}

      {demoRefusal && !uploading ? (
        <DemoReadOnlyNotice action={demoRefusal.action} className="mt-3" />
      ) : (
        errorText && !uploading && <ImportError title="The subject could not be imported" message={errorText} />
      )}
      {subject.isError && !data && !uploading && !(isApiError(subject.error) && subject.error.status === 404) && (
        <ImportError title="The selected subject could not be loaded" message={errorMessage(subject.error)}>
          <Button size="sm" variant="secondary" onClick={() => void subject.refetch()}>
            <RefreshCw aria-hidden />
            Retry
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onSelect(null)}>
            Import another subject
          </Button>
        </ImportError>
      )}
    </ImportCard>
  )
}

export function BusyContent({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-3" role="status">
      <div className="flex size-10 items-center justify-center rounded-full border border-accent/40 bg-accent/10">
        <Spinner className="text-accent-fg" label="Importing" />
      </div>
      <div className="space-y-1">
        <p className="max-w-full truncate text-sm font-medium text-fg">{title}</p>
        {hint && <p className="text-xs text-fg-subtle">{hint}</p>}
      </div>
      <ProgressBar size="xs" label={title} className="w-40" />
    </div>
  )
}

function SubjectSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading subject">
      <Skeleton className="h-5 w-3/4" />
      <Skeleton className="h-3.5 w-1/2" />
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </div>
    </div>
  )
}

function SubjectSummary({ subject, onFiles }: { subject: SubjectView; onFiles: (files: File[]) => void }) {
  const { stats } = subject
  const errors = subject.validation.filter((i) => i.level === 'error')
  const warnings = subject.validation.filter((i) => i.level === 'warning')
  const warningCount = warnings.length + subject.warnings.length
  const issueList = [...errors.map((i) => i.message), ...warnings.map((i) => i.message), ...subject.warnings]

  return (
    <DropZone onFiles={onFiles} accept={SUBJECT_ACCEPT} inputLabel="Replace subject file">
      {({ dragging, browse }) => (
        <div
          className={cn(
            'flex flex-col gap-4 rounded-xl transition-colors',
            dragging && 'outline-2 outline-offset-4 outline-accent outline-dashed',
          )}
        >
          <div className="min-w-0">
            <p className="line-clamp-2 text-base leading-snug font-semibold text-fg" title={subject.title}>
              {subject.title || subject.source_name}
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-fg-muted">
              <span className="inline-flex min-w-0 items-center gap-1">
                <FileText className="size-3.5 shrink-0" aria-hidden />
                <span className="truncate font-mono text-2xs">{subject.source_name}</span>
              </span>
              <Badge tone="neutral">{MEDIA_LABEL[subject.media_type] ?? subject.media_type}</Badge>
              <Badge tone="info">{capitalize(stats.language || 'python')}</Badge>
              {subject.parser && subject.parser !== 'heuristic' && <Badge tone="accent">{subject.parser}</Badge>}
            </div>
          </div>

          <div className="@container">
          <dl className="grid grid-cols-3 gap-2 @md:grid-cols-5">
            <MiniStat label="Exercises" value={stats.exercises} hint={`${stats.mandatory_exercises} mandatory`} />
            <MiniStat label="Functions" value={stats.functions} />
            <MiniStat
              label="Known tests"
              value={stats.known_tests}
              hint={stats.script_tests ? `incl. ${stats.script_tests} runs` : undefined}
            />
            <MiniStat label="Constraints" value={stats.constraints} />
            <MiniStat label="Bonus" value={stats.bonus_exercises} tone={stats.bonus_exercises ? 'bonus' : undefined} />
          </dl>
          </div>

          <Validity errors={errors.length} warnings={warningCount} details={issueList} />

          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
            <Link
              to={`/subjects/${encodeURIComponent(subject.id)}`}
              className="group inline-flex items-center gap-1 rounded-sm text-sm font-medium text-accent-fg hover:underline hover:underline-offset-4"
            >
              Review extracted requirements
              <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
            </Link>
            <Button size="sm" variant="ghost" onClick={browse}>
              <RefreshCw aria-hidden />
              Replace
            </Button>
          </div>
        </div>
      )}
    </DropZone>
  )
}

function Validity({ errors, warnings, details }: { errors: number; warnings: number; details: string[] }) {
  const tooltip = details.length ? (
    <ul className="list-disc space-y-0.5 pl-4">
      {details.slice(0, 5).map((d, i) => (
        <li key={i}>{d}</li>
      ))}
      {details.length > 5 && <li>…and {details.length - 5} more (see the review page)</li>}
    </ul>
  ) : null

  const content =
    errors > 0 ? (
      <span className="inline-flex items-center gap-1.5 text-fail">
        <CircleAlert className="size-4" aria-hidden />
        {errors} validation {errors === 1 ? 'error' : 'errors'}
        {warnings > 0 && <span className="text-warning">· {warnings} {warnings === 1 ? 'warning' : 'warnings'}</span>}
      </span>
    ) : warnings > 0 ? (
      <span className="inline-flex items-center gap-1.5 text-warning">
        <TriangleAlert className="size-4" aria-hidden />
        Contract extracted · {warnings} {warnings === 1 ? 'warning' : 'warnings'} to review
      </span>
    ) : (
      <span className="inline-flex items-center gap-1.5 text-pass">
        <CircleCheck className="size-4" aria-hidden />
        Contract extracted · no validation issues
      </span>
    )

  return (
    <div className="flex items-center rounded-lg border border-border bg-bg-subtle/60 px-3 py-2 text-xs font-medium" data-testid="subject-validity">
      {tooltip ? (
        <Tooltip content={tooltip} side="bottom" align="start">
          <span tabIndex={0} className="rounded-sm">
            {content}
          </span>
        </Tooltip>
      ) : (
        content
      )}
    </div>
  )
}

export function MiniStat({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: number | string
  hint?: string
  tone?: 'bonus' | 'pass' | 'warning'
}) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-surface-2/50 px-2.5 py-2">
      <dt className="truncate text-2xs font-medium text-fg-subtle">{label}</dt>
      <dd
        className={cn(
          'tabular text-lg leading-tight font-semibold text-fg',
          tone === 'bonus' && 'text-bonus',
          tone === 'pass' && 'text-pass',
          tone === 'warning' && 'text-warning',
        )}
      >
        {value}
      </dd>
      {hint && <dd className="truncate text-2xs text-fg-subtle">{hint}</dd>}
    </div>
  )
}

function capitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}
