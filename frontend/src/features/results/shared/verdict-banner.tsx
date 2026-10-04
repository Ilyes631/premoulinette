import { ArrowRight, CircleCheckBig, TriangleAlert } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { Button } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { ScoreSummary } from '@/lib/types'
import { verdictCopy } from './meta'

interface VerdictBannerProps {
  score: ScoreSummary
  onPrimary?: () => void
  primaryLabel?: string
  /** Mandatory failures of critical severity (computed from the checks). */
  criticalFailures?: number
}

/** The answer to "can I push now?" — deliberately the loudest element of the page. */
export function VerdictBanner({ score, onPrimary, primaryLabel, criticalFailures = 0 }: VerdictBannerProps) {
  const reduce = useReducedMotion()
  const ready = score.verdict === 'ready'
  const { title, message } = verdictCopy(score)
  const Icon = ready ? CircleCheckBig : TriangleAlert
  const critical = criticalFailures
  return (
    <motion.section
      role="status"
      aria-label={`Verdict: ${title}`}
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.25, 1, 0.5, 1] }}
      className={cn(
        'relative overflow-hidden rounded-xl border px-4 py-4 sm:px-5',
        ready ? 'border-pass/30 bg-pass/[0.07]' : 'border-fail/30 bg-fail/[0.07]',
      )}
      data-verdict={score.verdict}
    >
      <div
        aria-hidden
        className={cn('absolute inset-y-0 left-0 w-1', ready ? 'bg-pass' : 'bg-fail')}
      />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 items-start gap-3.5">
          <span
            className={cn(
              'flex size-10 shrink-0 items-center justify-center rounded-lg border',
              ready ? 'border-pass/30 bg-pass/10 text-pass' : 'border-fail/30 bg-fail/10 text-fail',
            )}
          >
            <Icon className="size-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <h2
              className={cn(
                'text-base font-bold tracking-[0.08em] sm:text-lg',
                ready ? 'text-pass' : 'text-fail',
              )}
            >
              {title}
            </h2>
            <p className="mt-0.5 text-sm text-pretty text-fg">{message}</p>
            {!ready && critical > 0 && (
              <p className="mt-1 text-xs text-fg-muted">
                <span className="tabular">{critical}</span> critical {critical === 1 ? 'issue' : 'issues'} among them —
                fix those first.
              </p>
            )}
          </div>
        </div>
        {onPrimary && primaryLabel && (
          <Button variant={ready ? 'secondary' : 'danger'} onClick={onPrimary} className="self-start sm:self-center">
            {primaryLabel}
            <ArrowRight aria-hidden />
          </Button>
        )}
      </div>
    </motion.section>
  )
}
