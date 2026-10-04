import { CircleCheck, CircleX, Info, TriangleAlert, X } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { cn } from '@/lib/cn'
import { dismissToast, useToasts, type ToastTone } from '@/lib/toast'

const ICON: Record<ToastTone, { Icon: typeof Info; className: string }> = {
  neutral: { Icon: Info, className: 'text-fg-muted' },
  success: { Icon: CircleCheck, className: 'text-pass' },
  error: { Icon: CircleX, className: 'text-fail' },
  warning: { Icon: TriangleAlert, className: 'text-warning' },
}

/** Renders the toast queue. Mount once (AppShell). */
export function Toaster() {
  const toasts = useToasts()
  const reduce = useReducedMotion()
  return (
    <div
      aria-live="polite"
      aria-relevant="additions"
      className="pointer-events-none fixed right-0 bottom-0 z-[60] flex w-full max-w-sm flex-col gap-2 p-4"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const { Icon, className } = ICON[t.tone]
          return (
            <motion.div
              key={t.id}
              layout={!reduce}
              initial={reduce ? false : { opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, x: 24, transition: { duration: 0.15 } }}
              transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
              role={t.tone === 'error' ? 'alert' : 'status'}
              className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border-strong bg-surface-3 p-3 shadow-pop"
            >
              <Icon className={cn('mt-0.5 size-4 shrink-0', className)} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-fg">{t.title}</p>
                {t.description && <p className="mt-0.5 text-xs break-words text-fg-muted">{t.description}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(t.id)}
                aria-label="Dismiss notification"
                className="-m-1 inline-flex size-6 shrink-0 items-center justify-center rounded text-fg-subtle hover:bg-surface-2 hover:text-fg"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
