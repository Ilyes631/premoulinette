import { Bot, FileText, TriangleAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Markdown } from '@/components/ui/markdown'
import { Skeleton } from '@/components/ui/misc'
import type { Explanation, ExplainMode } from '@/lib/types'

export interface ExplanationState {
  mode: ExplainMode
  status: 'loading' | 'success' | 'error'
  data?: Explanation
  error?: string
}

export const EXPLAIN_MODE_LABELS: Record<ExplainMode, string> = {
  explain: 'Explanation',
  fix: 'How to fix',
  expected: 'Expected behavior',
}

/** Renders a deterministic (template) or AI explanation of an existing check result. */
export function ExplanationPanel({ state }: { state: ExplanationState }) {
  return (
    <section
      aria-live="polite"
      aria-busy={state.status === 'loading'}
      aria-label={EXPLAIN_MODE_LABELS[state.mode]}
      className="rounded-lg border border-border bg-surface-2/50 p-4"
    >
      {state.status === 'loading' && (
        <div className="space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      )}
      {state.status === 'error' && (
        <p className="flex items-start gap-2 text-sm text-fail" role="alert">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {state.error ?? 'Could not load the explanation.'}
        </p>
      )}
      {state.status === 'success' && state.data && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-fg">{state.data.title || EXPLAIN_MODE_LABELS[state.mode]}</h3>
            {state.data.provider === 'ai' ? (
              <Badge tone="warning" variant="outline">
                <Bot aria-hidden /> AI · explains only, never grades
              </Badge>
            ) : (
              <Badge variant="outline">
                <FileText aria-hidden /> Offline template
              </Badge>
            )}
          </div>
          <Markdown source={state.data.markdown} />
        </>
      )}
    </section>
  )
}
