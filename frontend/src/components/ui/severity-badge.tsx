import { SEVERITY_LABELS } from '@/lib/check-meta'
import { cn } from '@/lib/cn'
import type { Severity } from '@/lib/types'

const LEVEL: Record<Severity, number> = { critical: 3, major: 2, minor: 1, style: 0 }

const TONE: Record<Severity, string> = {
  critical: 'border-sev-critical/30 bg-sev-critical/10 text-sev-critical',
  major: 'border-sev-major/30 bg-sev-major/10 text-sev-major',
  minor: 'border-border-strong bg-surface-2 text-sev-minor',
  style: 'border-dashed border-border-strong bg-transparent text-sev-style',
}

/** Three-bar signal glyph: severity is readable without color. */
function SeverityBars({ level }: { level: number }) {
  return (
    <svg viewBox="0 0 12 12" className="size-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <rect
          key={i}
          x={1 + i * 4}
          y={8 - i * 3}
          width={2.5}
          height={3 + i * 3}
          rx={0.75}
          fill="currentColor"
          opacity={i < level ? 1 : 0.25}
        />
      ))}
    </svg>
  )
}

export interface SeverityBadgeProps {
  severity: Severity
  className?: string
  size?: 'sm' | 'md'
}

export function SeverityBadge({ severity, className, size = 'sm' }: SeverityBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md border font-medium leading-none',
        size === 'sm' ? 'h-5 px-1.5 text-2xs' : 'h-6 px-2 text-xs',
        TONE[severity],
        className,
      )}
    >
      <SeverityBars level={LEVEL[severity]} />
      {SEVERITY_LABELS[severity]}
    </span>
  )
}
