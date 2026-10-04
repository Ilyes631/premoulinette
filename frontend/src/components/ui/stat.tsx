import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

const TONE: Record<string, string> = {
  neutral: 'text-fg',
  pass: 'text-pass',
  fail: 'text-fail',
  warning: 'text-warning',
  info: 'text-info',
  bonus: 'text-bonus',
  accent: 'text-accent-fg',
}

export interface StatProps {
  label: ReactNode
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  tone?: keyof typeof TONE
  className?: string
}

/** Compact KPI tile: label, big tabular value, optional hint. */
export function Stat({ label, value, hint, icon: Icon, tone = 'neutral', className }: StatProps) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-1 rounded-lg border border-border bg-surface-2/60 px-3.5 py-3', className)}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-fg-muted">
        {Icon && <Icon className="size-3.5 shrink-0" aria-hidden />}
        <span className="truncate">{label}</span>
      </div>
      <div className={cn('tabular text-xl font-semibold tracking-tight', TONE[tone])}>{value}</div>
      {hint && <div className="truncate text-xs text-fg-subtle">{hint}</div>}
    </div>
  )
}
