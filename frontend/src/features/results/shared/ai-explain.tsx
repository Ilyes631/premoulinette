import { Bot, Send, ShieldQuestion } from 'lucide-react'
import { useId, useState } from 'react'
import { Button, CodeBlock, Skeleton } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/cn'
import { useAiPayload } from '@/lib/queries'
import type { CheckResult } from '@/lib/types'

type AiMode = 'explain' | 'fix'

interface AiExplainProps {
  analysisId: string
  check: CheckResult
  busy: boolean
  onSend: (mode: AiMode) => void
}

/**
 * Optional "Ask AI" flow (only offered when AI is enabled in the settings): shows the exact minimal
 * payload that would be sent, and requires an explicit consent tick before anything leaves the machine.
 * The AI only explains the deterministic result; it never changes pass/fail.
 */
export function AiExplain({ analysisId, check, busy, onSend }: AiExplainProps) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<AiMode>('explain')
  const [consent, setConsent] = useState(false)
  const payload = useAiPayload(analysisId, check.id, mode, open)
  const consentId = useId()

  if (!open) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border-strong px-3 py-2.5">
        <Bot className="size-4 text-fg-subtle" aria-hidden />
        <p className="min-w-0 flex-1 text-xs text-fg-muted">
          Prefer a tailored explanation? You can ask the AI — you will see exactly what is sent first.
        </p>
        <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
          Ask AI…
        </Button>
      </div>
    )
  }

  return (
    <section aria-label="Ask AI" className="space-y-3 rounded-lg border border-warning/25 bg-warning/[0.04] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Bot className="size-4 text-warning" aria-hidden />
        <h3 className="text-sm font-semibold text-fg">Ask AI</h3>
        <div className="ml-auto inline-flex rounded-md border border-border bg-bg-subtle p-0.5" role="group" aria-label="AI request type">
          {(['explain', 'fix'] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => {
                setMode(m)
                setConsent(false)
              }}
              className={cn(
                'h-6 rounded px-2 text-xs font-medium text-fg-muted transition-colors',
                mode === m && 'bg-surface-3 text-fg shadow-card',
              )}
            >
              {m === 'explain' ? 'Explain' : 'How to fix'}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-fg-muted">
        Exactly this payload would be sent to Anthropic — never your whole repository:
      </p>
      {payload.isPending && <Skeleton className="h-28 w-full" />}
      {payload.isError && (
        <p role="alert" className="flex items-start gap-1.5 text-xs text-fail">
          <ShieldQuestion className="mt-px size-3.5 shrink-0" aria-hidden />
          {errorMessage(payload.error)}
        </p>
      )}
      {payload.data && (
        <CodeBlock
          code={JSON.stringify(payload.data, null, 2)}
          language="text"
          showLineNumbers={false}
          maxHeight="16rem"
          title="Payload preview"
        />
      )}
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor={consentId} className="flex min-w-0 flex-1 cursor-pointer items-start gap-2 text-xs text-fg">
          <input
            id={consentId}
            type="checkbox"
            checked={consent}
            disabled={!payload.data}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 size-3.5 accent-[var(--pm-accent)]"
          />
          I agree to send exactly this payload to the AI provider.
        </label>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" disabled={!consent || !payload.data} loading={busy} onClick={() => onSend(mode)}>
          {!busy && <Send aria-hidden />}
          Send to AI
        </Button>
      </div>
    </section>
  )
}
