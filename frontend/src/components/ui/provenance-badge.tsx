import { UserRound } from 'lucide-react'
import { PROVENANCE_META } from '@/lib/check-meta'
import { cn } from '@/lib/cn'
import type { Provenance } from '@/lib/types'
import { Tooltip } from './tooltip'

const STYLE: Record<Provenance, string> = {
  explicit: 'border-transparent bg-fg/10 text-fg',
  derived: 'border-accent-fg/45 bg-transparent text-accent-fg',
  heuristic: 'border-dashed border-fg-subtle/60 bg-transparent text-fg-subtle',
  ai_extracted: 'border-warning/30 bg-warning/10 text-warning',
  user: 'border-info/30 bg-transparent text-info',
}

export interface ProvenanceBadgeProps {
  provenance: Provenance
  /** 0..1 — shown when below 1 (or always with `showConfidence`). */
  confidence?: number
  showConfidence?: boolean
  className?: string
}

export function ProvenanceBadge({ provenance, confidence, showConfidence, className }: ProvenanceBadgeProps) {
  const meta = PROVENANCE_META[provenance]
  const pct = confidence === undefined ? null : Math.round(confidence * 100)
  const withConfidence = pct !== null && (showConfidence || pct < 100)
  const tooltip = withConfidence ? `${meta.tooltip} · Confidence ${pct}%` : meta.tooltip
  return (
    <Tooltip content={tooltip}>
      <span
        className={cn(
          'inline-flex h-5 shrink-0 items-center gap-1 whitespace-nowrap rounded-md border px-1.5 text-2xs font-medium leading-none',
          STYLE[provenance],
          className,
        )}
      >
        {provenance === 'ai_extracted' && <span className="size-1.5 rounded-full bg-warning" aria-hidden />}
        {provenance === 'user' && <UserRound className="size-3" aria-hidden />}
        {meta.label}
        {withConfidence && <span className="tabular opacity-75">{pct}%</span>}
        <span className="sr-only">. {tooltip}</span>
      </span>
    </Tooltip>
  )
}
