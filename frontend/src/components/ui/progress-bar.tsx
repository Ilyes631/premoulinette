import { cn } from '@/lib/cn'

const FILL: Record<string, string> = {
  accent: 'bg-accent',
  pass: 'bg-pass',
  fail: 'bg-fail',
  warning: 'bg-warning',
  info: 'bg-info',
  bonus: 'bg-bonus',
}

export interface ProgressBarProps {
  /** 0..100; undefined renders an indeterminate bar. */
  value?: number
  tone?: keyof typeof FILL
  size?: 'xs' | 'sm' | 'md'
  label: string
  className?: string
}

export function ProgressBar({ value, tone = 'accent', size = 'sm', label, className }: ProgressBarProps) {
  const indeterminate = value === undefined
  const clamped = indeterminate ? 0 : Math.min(100, Math.max(0, value))
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(clamped)}
      className={cn(
        'relative w-full overflow-hidden rounded-full bg-fg/10',
        size === 'xs' ? 'h-1' : size === 'sm' ? 'h-1.5' : 'h-2',
        className,
      )}
    >
      {indeterminate ? (
        <div
          className={cn('absolute inset-0 animate-shimmer opacity-80', FILL[tone])}
          style={{
            backgroundImage: 'linear-gradient(90deg, transparent 0%, rgb(255 255 255 / 0.35) 50%, transparent 100%)',
            backgroundSize: '200% 100%',
          }}
        />
      ) : (
        <div
          className={cn('h-full origin-left rounded-full transition-transform duration-300 ease-out', FILL[tone])}
          style={{ transform: `scaleX(${clamped / 100})` }}
        />
      )}
    </div>
  )
}
