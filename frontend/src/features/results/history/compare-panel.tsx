import { ArrowDownRight, ArrowUpRight, CircleCheck, CircleX, GitCompareArrows, Minus } from 'lucide-react'
import type { ReactNode } from 'react'
import { Skeleton, StatusIcon } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/cn'
import { formatLocation } from '@/lib/format'
import { useComparison } from '@/lib/queries'
import type { AnalysisListItem, CheckChange } from '@/lib/types'
import { useResults } from '../shared/results-context'
import { formatDelta } from '../shared/meta'
import { SectionCard } from '../shared/section-card'

export function ComparePanel({ base }: { base: AnalysisListItem }) {
  const { report } = useResults()
  const comparison = useComparison(report.id, base.id)
  const data = comparison.data
  return (
    <SectionCard
      icon={GitCompareArrows}
      title={`Compared with analysis #${base.number}`}
      description="Checks are matched by their stable id across analyses."
    >
      {comparison.isPending && (
        <div className="space-y-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}
      {comparison.isError && (
        <p role="alert" className="text-sm text-fail">
          {errorMessage(comparison.error)}
        </p>
      )}
      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <DeltaTile
              label="Readiness"
              value={formatDelta(data.readiness_delta)}
              tone={data.readiness_delta > 0 ? 'pass' : data.readiness_delta < 0 ? 'fail' : 'neutral'}
              icon={data.readiness_delta > 0 ? ArrowUpRight : data.readiness_delta < 0 ? ArrowDownRight : Minus}
            />
            <DeltaTile label="Fixed" value={`+${data.fixed.length}`} tone={data.fixed.length ? 'pass' : 'neutral'} icon={CircleCheck} />
            <DeltaTile
              label="New failures"
              value={data.new_failures.length ? `−${data.new_failures.length}` : '0'}
              tone={data.new_failures.length ? 'fail' : 'neutral'}
              icon={CircleX}
            />
            <DeltaTile label="Still failing" value={String(data.still_failing.length)} tone="neutral" icon={Minus} />
          </div>
          <p className="text-sm text-fg">
            <span className="font-medium text-pass">
              +{data.fixed.length} {data.fixed.length === 1 ? 'check' : 'checks'} fixed
            </span>
            <span className="text-fg-subtle"> · </span>
            <span className={cn('font-medium', data.new_failures.length ? 'text-fail' : 'text-fg-muted')}>
              {data.new_failures.length ? '−' : ''}
              {data.new_failures.length} new {data.new_failures.length === 1 ? 'failure' : 'failures'}
            </span>
          </p>
          <ChangeList title="Fixed" changes={data.fixed} empty="Nothing was fixed since this analysis." />
          <ChangeList title="New failures" changes={data.new_failures} empty="No regression." />
          <ChangeList title="Still failing" changes={data.still_failing} empty="Nothing left over." />
          {(data.new_checks.length > 0 || data.removed_checks.length > 0) && (
            <p className="text-xs text-fg-subtle">
              {data.new_checks.length} new and {data.removed_checks.length} removed checks (the subject contract changed
              between the two analyses).
            </p>
          )}
        </div>
      )}
    </SectionCard>
  )
}

function DeltaTile({
  label,
  value,
  tone,
  icon: Icon,
}: {
  label: string
  value: ReactNode
  tone: 'pass' | 'fail' | 'neutral'
  icon: typeof Minus
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2.5">
      <p className="text-2xs font-medium text-fg-muted">{label}</p>
      <p
        className={cn(
          'mt-0.5 flex items-center gap-1 text-lg font-semibold tabular',
          tone === 'pass' ? 'text-pass' : tone === 'fail' ? 'text-fail' : 'text-fg',
        )}
      >
        <Icon className="size-4" aria-hidden />
        {value}
      </p>
    </div>
  )
}

function ChangeList({ title, changes, empty }: { title: string; changes: CheckChange[]; empty: string }) {
  const { openCheck, report } = useResults()
  const known = new Set(report.checks.map((c) => c.id))
  return (
    <section aria-label={title}>
      <h4 className="mb-1.5 text-xs font-semibold tracking-wider text-fg-subtle uppercase">
        {title} <span className="tabular">({changes.length})</span>
      </h4>
      {changes.length === 0 ? (
        <p className="text-xs text-fg-subtle">{empty}</p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {changes.map((c) => {
            const inReport = known.has(c.id)
            const content = (
              <>
                <span className="flex shrink-0 items-center gap-1" role="img" aria-label={`${c.before ?? 'absent'} to ${c.after ?? 'absent'}`}>
                  {c.before ? <StatusIcon status={c.before} label="" /> : <Minus className="size-4 text-fg-subtle" aria-hidden />}
                  <span className="text-fg-subtle" aria-hidden>
                    →
                  </span>
                  {c.after ? <StatusIcon status={c.after} label="" /> : <Minus className="size-4 text-fg-subtle" aria-hidden />}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-fg">{c.title}</span>
                {c.file && <span className="hidden shrink-0 font-mono text-2xs text-fg-subtle sm:inline">{formatLocation({ file: c.file, line: null })}</span>}
              </>
            )
            return (
              <li key={c.id}>
                {inReport ? (
                  <button
                    type="button"
                    onClick={() => openCheck(c.id, changes.map((x) => x.id).filter((id) => known.has(id)))}
                    className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-surface-2"
                  >
                    {content}
                  </button>
                ) : (
                  <div className="flex items-center gap-3 px-3 py-2">{content}</div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
