import { CircleAlert, CircleCheck, LoaderCircle, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui'
import { cn } from '@/lib/cn'

export type ImportState = 'empty' | 'loading' | 'uploading' | 'ready' | 'error'

const STATE_BADGE: Record<ImportState, ReactNode> = {
  empty: (
    <Badge tone="neutral" variant="dashed">
      Not imported
    </Badge>
  ),
  loading: (
    <Badge tone="neutral">
      <LoaderCircle className="animate-spin" aria-hidden />
      Loading
    </Badge>
  ),
  uploading: (
    <Badge tone="accent">
      <LoaderCircle className="animate-spin" aria-hidden />
      Importing
    </Badge>
  ),
  ready: (
    <Badge tone="pass">
      <CircleCheck aria-hidden />
      Ready
    </Badge>
  ),
  error: (
    <Badge tone="fail">
      <CircleAlert aria-hidden />
      Error
    </Badge>
  ),
}

export interface ImportCardProps {
  step: number
  title: string
  description: string
  icon: LucideIcon
  state: ImportState
  /** Right side of the header, next to the state badge (e.g. a "Replace" button). */
  actions?: ReactNode
  children: ReactNode
  className?: string
  labelId: string
}

/** Shared chrome of the SUBJECT and STUDENT PROJECT cards. */
export function ImportCard({
  step,
  title,
  description,
  icon: Icon,
  state,
  actions,
  children,
  className,
  labelId,
}: ImportCardProps) {
  return (
    <section
      aria-labelledby={labelId}
      data-state={state}
      className={cn(
        'group/card relative flex min-w-0 flex-col rounded-2xl border bg-surface shadow-card transition-[border-color,box-shadow] duration-200',
        state === 'ready' ? 'border-pass/25' : state === 'error' ? 'border-fail/30' : 'border-border',
        className,
      )}
    >
      {state === 'ready' && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-6 -top-px h-px bg-gradient-to-r from-transparent via-pass/60 to-transparent"
        />
      )}
      <header className="flex items-start gap-3 px-5 pt-5 pb-4">
        <div
          aria-hidden
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-lg border shadow-card',
            state === 'ready' ? 'border-pass/25 bg-pass/10 text-pass' : 'border-border-strong bg-surface-2 text-fg-muted',
          )}
        >
          <Icon className="size-4.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="tabular font-mono text-2xs font-medium tracking-wider text-fg-subtle uppercase">
              Step {step}
            </span>
          </div>
          <h2 id={labelId} className="text-[0.95rem] leading-tight font-semibold text-fg">
            {title}
          </h2>
          <p className="mt-0.5 text-xs text-fg-muted">{description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {actions}
          <span aria-live="polite">{STATE_BADGE[state]}</span>
        </div>
      </header>
      <div className="flex flex-1 flex-col px-5 pb-5">{children}</div>
    </section>
  )
}

/** Inline error block used inside the import cards. */
export function ImportError({ title, message, children }: { title: string; message: string; children?: ReactNode }) {
  return (
    <div role="alert" className="mt-3 flex items-start gap-2.5 rounded-lg border border-fail/25 bg-fail/[0.07] px-3 py-2.5 text-sm">
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-fail" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-fail">{title}</p>
        <p className="mt-0.5 break-words text-fg-muted">{message}</p>
        {children && <div className="mt-2 flex flex-wrap gap-2">{children}</div>}
      </div>
    </div>
  )
}
