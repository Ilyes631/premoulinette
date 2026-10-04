import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface EmptyStateProps {
  icon?: LucideIcon
  title: ReactNode
  description?: ReactNode
  /** Buttons / links. */
  children?: ReactNode
  className?: string
  tone?: 'neutral' | 'fail'
}

export function EmptyState({ icon: Icon, title, description, children, className, tone = 'neutral' }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-border-strong px-6 py-14 text-center',
        className,
      )}
    >
      {Icon && (
        <div
          className={cn(
            'mb-4 flex size-11 items-center justify-center rounded-xl border bg-surface-2 shadow-card',
            tone === 'fail' ? 'border-fail/30 text-fail' : 'border-border-strong text-fg-muted',
          )}
        >
          <Icon className="size-5" aria-hidden />
        </div>
      )}
      <h2 className="text-base font-semibold text-fg">{title}</h2>
      {description && <p className="mt-1.5 max-w-md text-sm text-pretty text-fg-muted">{description}</p>}
      {children && <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{children}</div>}
    </div>
  )
}
