import { Check, X } from 'lucide-react'
import { motion } from 'motion/react'
import { cn } from '@/lib/cn'
import type { JobStage, StageStatus } from '@/lib/types'

const STATUS_TEXT: Record<StageStatus, string> = {
  pending: 'pending',
  running: 'in progress',
  done: 'done',
  error: 'failed',
}

/** Vertical stepper of the analysis stages (ARCHITECTURE.md engine STAGES). */
export function StageStepper({ stages }: { stages: JobStage[] }) {
  return (
    <ol aria-label="Analysis stages" className="flex flex-col">
      {stages.map((stage, index) => {
        const last = index === stages.length - 1
        return (
          <motion.li
            key={stage.key}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.22, delay: index * 0.03 }}
            aria-current={stage.status === 'running' ? 'step' : undefined}
            data-status={stage.status}
            className="relative flex gap-3.5 pb-4 last:pb-0"
          >
            {!last && (
              <span
                aria-hidden
                className={cn(
                  'absolute top-7 bottom-1 left-[11px] w-px transition-colors duration-300',
                  stage.status === 'done' ? 'bg-pass/45' : 'bg-border-strong',
                )}
              />
            )}
            <StageIcon status={stage.status} />
            <div className="flex min-w-0 flex-1 items-center justify-between gap-3 pt-0.5">
              <span
                className={cn(
                  'truncate text-sm transition-colors duration-200',
                  stage.status === 'running' && 'font-medium text-fg',
                  stage.status === 'done' && 'text-fg-muted',
                  stage.status === 'pending' && 'text-fg-subtle',
                  stage.status === 'error' && 'font-medium text-fail',
                )}
              >
                {stage.label}
              </span>
              <span
                className={cn(
                  'shrink-0 text-2xs font-medium',
                  stage.status === 'running' ? 'text-accent-fg' : stage.status === 'error' ? 'text-fail' : 'text-fg-subtle',
                  stage.status === 'pending' && 'sr-only',
                  stage.status === 'done' && 'sr-only',
                )}
              >
                {STATUS_TEXT[stage.status]}
              </span>
            </div>
          </motion.li>
        )
      })}
    </ol>
  )
}

function StageIcon({ status }: { status: StageStatus }) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full border transition-colors duration-300',
        status === 'pending' && 'border-border-strong bg-surface',
        status === 'running' && 'border-accent/60 bg-accent/15',
        status === 'done' && 'border-pass/40 bg-pass/15 text-pass',
        status === 'error' && 'border-fail/50 bg-fail/15 text-fail',
      )}
    >
      {status === 'pending' && <span className="size-1.5 rounded-full bg-fg-subtle/60" />}
      {status === 'running' && (
        <>
          <span className="absolute inset-0 animate-ping rounded-full border border-accent/40 motion-reduce:hidden" />
          <span className="size-3 animate-spin rounded-full border-2 border-accent-fg/30 border-t-accent-fg" />
        </>
      )}
      {status === 'done' && (
        <motion.span initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 28 }}>
          <Check className="size-3.5" strokeWidth={3} />
        </motion.span>
      )}
      {status === 'error' && <X className="size-3.5" strokeWidth={3} />}
    </span>
  )
}
