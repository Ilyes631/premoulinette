import { ChevronRight, ChevronsDownUp, ChevronsUpDown, FileText, Info, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { CheckRow } from '@/components/results'
import { Badge, Button, Card } from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatDateTime, formatPercent } from '@/lib/format'
import { exerciseStatusMeta } from '../shared/meta'
import { ExportButtons } from '../shared/export-menu'
import { useResults } from '../shared/results-context'
import { buildReportSections, type ReportSection, type SectionTone } from './report-sections'

const DOT: Record<SectionTone, string> = {
  pass: 'bg-pass',
  fail: 'bg-fail',
  warning: 'bg-warning',
  bonus: 'bg-bonus',
  neutral: 'bg-fg-subtle/50',
}

export function ReportTab() {
  const { report } = useResults()
  const sections = useMemo(() => buildReportSections(report), [report])
  const [open, setOpen] = useState<ReadonlySet<string>>(
    () => new Set(sections.filter((s) => s.tone === 'fail' || s.id === 'repository' || s.id === 'mandatory').map((s) => s.id)),
  )
  const allOpen = open.size === sections.length

  const setSection = (id: string, value: boolean) =>
    setOpen((prev) => {
      if (prev.has(id) === value) return prev
      const next = new Set(prev)
      if (value) next.add(id)
      else next.delete(id)
      return next
    })

  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-fg">
            <FileText className="size-4 text-fg-subtle" aria-hidden />
            Analysis report #{report.number}
          </h2>
          <p className="mt-0.5 text-xs text-fg-muted">
            {formatDateTime(report.created_at)} · readiness{' '}
            <span className="font-medium text-fg tabular">{formatPercent(report.score.readiness, 1)}</span> ·{' '}
            {report.score.verdict === 'ready' ? 'ready to submit' : 'not ready'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ExportButtons analysisId={report.id} />
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setOpen(allOpen ? new Set() : new Set(sections.map((s) => s.id)))}
          >
            {allOpen ? <ChevronsDownUp aria-hidden /> : <ChevronsUpDown aria-hidden />}
            {allOpen ? 'Collapse all' : 'Expand all'}
          </Button>
        </div>
      </Card>
      <div className="space-y-2">
        {sections.map((s) => (
          <ReportSectionView key={s.id} section={s} open={open.has(s.id)} onOpenChange={(v) => setSection(s.id, v)} />
        ))}
      </div>
    </div>
  )
}

function ReportSectionView({
  section: s,
  open,
  onOpenChange,
}: {
  section: ReportSection
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { openCheck } = useResults()
  const ids = s.checks.map((c) => c.id)
  const isEmpty = s.facts.length + s.exercises.length + s.checks.length + s.notes.length === 0
  return (
    <details
      id={`report-${s.id}`}
      open={open}
      onToggle={(e) => onOpenChange(e.currentTarget.open)}
      className="group overflow-hidden rounded-xl border border-border bg-surface shadow-card"
    >
      <summary className="flex list-none items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-2/50 sm:px-5 [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-4 shrink-0 text-fg-subtle transition-transform group-open:rotate-90" aria-hidden />
        <span className={cn('size-2 shrink-0 rounded-full', DOT[s.tone])} aria-hidden />
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-fg">{s.title}</h3>
        <span className="hidden shrink-0 text-xs text-fg-muted tabular sm:inline">{s.summary}</span>
      </summary>
      <div className="space-y-4 border-t border-border px-4 py-4 sm:px-5">
        <p className="text-xs text-fg-muted tabular sm:hidden">{s.summary}</p>
        {s.facts.length > 0 && (
          <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            {s.facts.map((f) => (
              <div key={f.label} className="flex min-w-0 items-baseline justify-between gap-3 border-b border-border pb-1.5">
                <dt className="shrink-0 text-fg-muted">{f.label}</dt>
                <dd className="min-w-0 truncate text-right text-fg" title={f.value}>
                  {f.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
        {s.exercises.length > 0 && (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {s.exercises.map((ex) => {
              const meta = exerciseStatusMeta(ex)
              return (
                <li key={ex.exercise_id} className="flex items-center gap-3 px-3 py-2 text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-fg">{ex.title}</span>
                    <span className="block truncate font-mono text-2xs text-fg-subtle">{ex.file}</span>
                  </span>
                  {ex.bonus && ex.status === 'not_implemented' && (
                    <span className="hidden text-2xs text-fg-subtle md:inline">Impact on mandatory score: none</span>
                  )}
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                  <span className="w-12 text-right text-xs text-fg-muted tabular">{formatPercent(ex.score)}</span>
                </li>
              )
            })}
          </ul>
        )}
        {s.checks.length > 0 && (
          <ul className="-mx-2 divide-y divide-border">
            {s.checks.map((check) => (
              <li key={check.id}>
                <CheckRow check={check} onSelect={() => openCheck(check.id, ids)} />
              </li>
            ))}
          </ul>
        )}
        {s.notes.length > 0 && (
          <ul className="space-y-1.5 text-xs text-fg-muted">
            {s.notes.map((n) => (
              <li key={n} className="flex gap-1.5">
                {s.id === 'subject' ? (
                  <Info className="mt-px size-3.5 shrink-0 text-fg-subtle" aria-hidden />
                ) : (
                  <TriangleAlert className="mt-px size-3.5 shrink-0 text-warning" aria-hidden />
                )}
                {n}
              </li>
            ))}
          </ul>
        )}
        {isEmpty && <p className="text-sm text-fg-subtle">{s.empty}</p>}
      </div>
    </details>
  )
}
