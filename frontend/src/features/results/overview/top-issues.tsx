import { ArrowRight, CircleCheckBig, ListTodo } from 'lucide-react'
import { useMemo } from 'react'
import { CheckRow } from '@/components/results'
import { Button } from '@/components/ui'
import type { CheckResult } from '@/lib/types'
import { useResults } from '../shared/results-context'
import { SectionCard } from '../shared/section-card'
import { isIssue, topIssues } from '../shared/selectors'

export function TopIssues({ checks }: { checks: CheckResult[] }) {
  const { openCheck, goToTab } = useResults()
  const top = useMemo(() => topIssues(checks, 5), [checks])
  const total = useMemo(() => checks.filter(isIssue).length, [checks])
  const ids = top.map((c) => c.id)
  return (
    <SectionCard
      icon={ListTodo}
      title="Fix these first"
      description="Blocking failures first, by severity."
      bodyClassName="px-2 sm:px-3"
      actions={
        total > 0 && (
          <Button size="sm" variant="ghost" onClick={() => goToTab('issues')}>
            All {total} issues <ArrowRight aria-hidden />
          </Button>
        )
      }
    >
      {top.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <CircleCheckBig className="size-6 text-pass" aria-hidden />
          <p className="text-sm font-medium text-fg">Nothing to fix</p>
          <p className="text-xs text-fg-muted">Every check that could be verified from the subject passed.</p>
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {top.map((check) => (
            <li key={check.id} data-nav-row>
              <CheckRow check={check} onSelect={() => openCheck(check.id, ids)} />
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
