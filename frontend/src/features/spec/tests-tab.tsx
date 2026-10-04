import { ArrowRight, FlaskConical, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { TranscriptView } from '@/components/results'
import { Badge, Button, EmptyState, ProvenanceBadge, Skeleton } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { useSubjectTests } from '@/lib/queries'
import type { GeneratedFunctionTest, GeneratedScriptTest } from '@/lib/types'
import { VisibleSpaces } from './parts'
import { formatCall, formatExpected } from './spec-utils'

function Group({
  title,
  description,
  count,
  tone,
  children,
}: {
  title: string
  description: ReactNode
  count: number
  tone?: 'neutral' | 'accent' | 'warning'
  children: ReactNode
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card" aria-label={title}>
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        <Badge tone={tone === 'warning' ? 'warning' : tone === 'accent' ? 'accent' : 'neutral'} className="tabular">
          {count}
        </Badge>
        <p className="w-full text-xs text-fg-muted sm:w-auto sm:flex-1 sm:text-right">{description}</p>
      </header>
      {count === 0 ? <p className="px-4 py-4 text-sm text-fg-subtle">Nothing in this group.</p> : children}
    </section>
  )
}

function FunctionRows({ tests }: { tests: GeneratedFunctionTest[] }) {
  return (
    <ul className="divide-y divide-border">
      {tests.map(({ test, exercise_id, rule }) => (
        <li key={test.id} className="grid gap-1 px-4 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.8125rem]">
            <code className="min-w-0 font-mono break-all text-fg">{formatCall(test)}</code>
            <ArrowRight className="size-3.5 shrink-0 text-fg-subtle" aria-label="expected" />
            <code className="min-w-0 font-mono break-all text-syn-string">{formatExpected(test)}</code>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:justify-end">
            <span className="font-mono text-2xs text-fg-subtle">{exercise_id}</span>
            <ProvenanceBadge provenance={test.origin.provenance} confidence={test.origin.confidence} showConfidence />
          </div>
          {(rule || test.origin.note) && (
            <p className="text-xs text-fg-muted sm:col-span-2">
              {rule && (
                <>
                  Rule <code className="font-mono text-fg">{rule}</code>
                </>
              )}
              {rule && test.origin.note && ' · '}
              {test.origin.note}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

function ScriptRows({ tests }: { tests: GeneratedScriptTest[] }) {
  return (
    <ul className="divide-y divide-border">
      {tests.map(({ test, exercise_id }) => {
        const inputs = test.stdin ? test.stdin.split('\n').filter((l, i, all) => l !== '' || i < all.length - 1) : []
        return (
          <li key={test.id} className="px-4 py-2.5">
            <details className="group">
              <summary className="flex flex-wrap items-center gap-2 text-[0.8125rem] marker:text-fg-subtle">
                <span className="font-medium text-fg">{test.title || test.id}</span>
                <span className="font-mono text-2xs text-fg-subtle">{exercise_id}</span>
                <span className="text-xs text-fg-muted">
                  stdin:{' '}
                  {inputs.length ? (
                    inputs.map((line, i) => (
                      <span key={i} className="mr-1 rounded bg-warning/10 px-1 font-mono text-warning">
                        <VisibleSpaces text={line} />
                      </span>
                    ))
                  ) : (
                    <span className="text-fg-subtle">empty</span>
                  )}
                </span>
                <span className="ml-auto">
                  <ProvenanceBadge provenance={test.origin.provenance} confidence={test.origin.confidence} showConfidence />
                </span>
              </summary>
              <div className="mt-2.5">
                {test.steps?.length ? (
                  <TranscriptView expected={test.steps} className="lg:grid-cols-1" />
                ) : (
                  <pre className="overflow-x-auto rounded-lg border border-border bg-code-bg px-3 py-2 font-mono text-xs text-fg">
                    {test.expected_stdout ?? 'No expected output (exit code only)'}
                  </pre>
                )}
              </div>
            </details>
          </li>
        )
      })}
    </ul>
  )
}

export function TestsTab({ subjectId }: { subjectId: string }) {
  const query = useSubjectTests(subjectId)
  if (query.isPending) {
    return (
      <div className="space-y-3" aria-busy>
        <Skeleton className="h-28" />
        <Skeleton className="h-40" />
      </div>
    )
  }
  if (query.isError) {
    return (
      <EmptyState icon={FlaskConical} tone="fail" title="Tests could not be generated" description={errorMessage(query.error)}>
        <Button onClick={() => void query.refetch()}>
          <RotateCw aria-hidden /> Retry
        </Button>
      </EmptyState>
    )
  }
  const { explicit, derived, heuristic, scripts } = query.data
  if (!explicit.length && !derived.length && !heuristic.length && !scripts.length) {
    return (
      <EmptyState
        icon={FlaskConical}
        title="No test can be generated yet"
        description="Add examples or rules to the functions, or sessions to the scripts, in the Requirements tab."
      />
    )
  }
  return (
    <div className="space-y-4">
      <Group title="Explicit" count={explicit.length} description="Examples written in the subject (official).">
        <FunctionRows tests={explicit} />
      </Group>
      <Group
        title="Derived"
        tone="accent"
        count={derived.length}
        description="Boundary cases computed deterministically from the subject's rules."
      >
        <FunctionRows tests={derived} />
      </Group>
      <Group title="Scripts" count={scripts.length} description="Terminal sessions: stdout is compared byte for byte.">
        <ScriptRows tests={scripts} />
      </Group>
      <Group
        title="Heuristic — not official"
        tone="warning"
        count={heuristic.length}
        description="Extra cases (0, negative, empty…) proposed by PréMoulinette. They never block the verdict."
      >
        <FunctionRows tests={heuristic} />
      </Group>
    </div>
  )
}
