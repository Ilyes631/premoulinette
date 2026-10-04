import { FlaskConical, SearchX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, EmptyState, ProvenanceBadge, StatusIcon } from '@/components/ui'
import { compareChecks } from '@/lib/check-meta'
import { cn } from '@/lib/cn'
import { formatDuration } from '@/lib/format'
import type { CheckResult } from '@/lib/types'
import { useResults } from '../shared/results-context'
import {
  isTestCheck,
  matchesTestStatus,
  shortValues,
  TEST_ORIGINS,
  testCallLabel,
  testOrigin,
  type TestOrigin,
  type TestStatusFilter,
} from '../shared/selectors'

const STATUS_OPTIONS: Array<{ value: TestStatusFilter; label: string }> = [
  { value: 'all', label: 'All results' },
  { value: 'failing', label: 'Not passing' },
  { value: 'passing', label: 'Passing' },
]

export function TestsTab() {
  const { report, openCheck } = useResults()
  const [searchParams] = useSearchParams()
  const selectedId = searchParams.get('check')
  const [origin, setOrigin] = useState<TestOrigin | 'all'>('all')
  const [status, setStatus] = useState<TestStatusFilter>('all')

  const tests = useMemo(() => report.checks.filter(isTestCheck).sort(compareChecks), [report.checks])
  const originCounts = useMemo(() => {
    const out: Record<TestOrigin, number> = { explicit: 0, derived: 0, heuristic: 0 }
    for (const t of tests) out[testOrigin(t)] += 1
    return out
  }, [tests])
  const rows = useMemo(
    () => tests.filter((t) => (origin === 'all' || testOrigin(t) === origin) && matchesTestStatus(t, status)),
    [origin, status, tests],
  )
  const ids = rows.map((r) => r.id)
  const passing = tests.filter((t) => matchesTestStatus(t, 'passing')).length

  if (tests.length === 0) {
    return (
      <EmptyState
        icon={FlaskConical}
        title="No tests were run"
        description="The subject has no examples or terminal sessions that could be turned into tests, or the files could not be loaded."
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by origin">
          {([{ value: 'all', label: 'All' }, ...TEST_ORIGINS] as Array<{ value: TestOrigin | 'all'; label: string }>).map(
            (o) => (
              <button
                key={o.value}
                type="button"
                aria-pressed={origin === o.value}
                onClick={() => setOrigin(o.value)}
                className="inline-flex h-8 items-center gap-1.5 rounded-full border border-border-strong px-3 text-xs font-medium text-fg-muted transition-colors hover:text-fg aria-pressed:border-accent-fg/40 aria-pressed:bg-accent/15 aria-pressed:text-fg"
              >
                {o.label}
                <span className="tabular opacity-75">{o.value === 'all' ? tests.length : originCounts[o.value]}</span>
              </button>
            ),
          )}
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-fg-muted">
            <span className="font-medium text-fg tabular">{passing}</span> / <span className="tabular">{tests.length}</span> passing
          </p>
          <label htmlFor="tests-status" className="sr-only">
            Result
          </label>
          <select
            id="tests-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as TestStatusFilter)}
            className="h-9 rounded-lg border border-border-strong bg-bg-subtle px-2.5 text-sm text-fg hover:bg-surface-2"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={SearchX} title="No test matches these filters" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm">
              <caption className="sr-only">Tests run in the sandbox</caption>
              <thead className="border-b border-border bg-surface-2/50 text-left text-2xs font-semibold tracking-wider text-fg-subtle uppercase">
                <tr>
                  <th scope="col" className="w-10 py-2 pl-4">
                    <span className="sr-only">Status</span>
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    Call / session
                  </th>
                  <th scope="col" className="hidden py-2 pr-3 sm:table-cell">
                    Origin
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    Expected
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    Actual
                  </th>
                  <th scope="col" className="hidden py-2 pr-4 text-right md:table-cell">
                    Time
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((check) => (
                  <TestRow
                    key={check.id}
                    check={check}
                    selected={check.id === selectedId}
                    onOpen={() => openCheck(check.id, ids)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <OriginLegend />
    </div>
  )
}

function TestRow({ check, selected, onOpen }: { check: CheckResult; selected: boolean; onOpen: () => void }) {
  const values = shortValues(check)
  const failing = !matchesTestStatus(check, 'passing')
  const ev = check.evidence
  return (
    <tr
      data-nav-row
      onClick={onOpen}
      aria-current={selected || undefined}
      className="cursor-pointer align-top transition-colors hover:bg-surface-2/60 aria-[current=true]:bg-surface-2"
    >
      <td className="py-2.5 pl-4">
        <StatusIcon status={check.status} className="mt-0.5" />
      </td>
      <td className="max-w-72 py-2.5 pr-3">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onOpen()
          }}
          className="block max-w-full truncate text-left font-mono text-xs text-fg hover:underline"
          title={testCallLabel(check)}
        >
          {testCallLabel(check)}
        </button>
        <span className="mt-0.5 block truncate text-2xs text-fg-subtle">{check.test_id ?? check.title}</span>
      </td>
      <td className="hidden py-2.5 pr-3 sm:table-cell">
        <ProvenanceBadge provenance={check.origin.provenance} confidence={check.origin.confidence} />
      </td>
      <td className="max-w-48 py-2.5 pr-3">
        <code className="block truncate font-mono text-xs text-fg-muted" title={values.expected ?? undefined}>
          {values.expected ?? '—'}
        </code>
      </td>
      <td className="max-w-48 py-2.5 pr-3">
        <code
          className={cn('block truncate font-mono text-xs', failing && values.actual ? 'text-fail' : 'text-fg-muted')}
          title={values.actual ?? undefined}
        >
          {values.actual ?? '—'}
        </code>
      </td>
      <td className="hidden py-2.5 pr-4 text-right text-xs text-fg-subtle tabular md:table-cell">
        {ev?.timed_out ? 'timeout' : formatDuration(ev?.duration_ms)}
      </td>
    </tr>
  )
}

function OriginLegend() {
  return (
    <section aria-label="Test origins" className="grid gap-3 rounded-lg border border-border p-4 sm:grid-cols-3">
      {TEST_ORIGINS.map((o) => (
        <div key={o.value} className="space-y-1.5">
          <ProvenanceBadge provenance={o.value} />
          <p className="text-xs text-pretty text-fg-muted">{o.description}</p>
        </div>
      ))}
    </section>
  )
}
