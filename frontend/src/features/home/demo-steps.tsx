import { Check } from 'lucide-react'
import { cn } from '@/lib/cn'

const STEPS = [
  { title: 'Load the demo project', text: 'A real TP subject and a student project with deliberate bugs.' },
  { title: 'Analyze', text: 'Follow the pipeline, then explore the readiness dashboard and open an issue.' },
  { title: 'Re-analyze', text: 'The fixed version reaches READY TO SUBMIT; History compares both runs.' },
] as const

/** Online demo only: the three-step path through the demo, the current step highlighted. */
export function DemoSteps({ loaded }: { loaded: boolean }) {
  const current = loaded ? 1 : 0
  return (
    <ol aria-label="Try the demo" className="grid gap-2 sm:grid-cols-3">
      {STEPS.map((step, i) => {
        const done = i < current
        const active = i === current
        return (
          <li
            key={step.title}
            aria-current={active ? 'step' : undefined}
            className={cn(
              'flex gap-3 rounded-xl border px-3.5 py-3 transition-colors',
              active ? 'border-accent/40 bg-accent/[0.07] shadow-card' : 'border-border bg-surface/50',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular',
                done && 'border-pass/30 bg-pass/15 text-pass',
                active && 'border-accent bg-accent text-accent-contrast',
                !done && !active && 'border-border-strong text-fg-subtle',
              )}
            >
              {done ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span className="min-w-0">
              <span className={cn('block text-sm font-medium', active || done ? 'text-fg' : 'text-fg-muted')}>
                {step.title}
              </span>
              <span className="mt-0.5 block text-xs leading-relaxed text-fg-muted">{step.text}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
