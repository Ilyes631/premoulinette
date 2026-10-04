import { cn } from '@/lib/cn'
import type { Verdict } from '@/lib/types'

export interface SparklineProps {
  /** Readiness values 0..100, oldest first. */
  values: number[]
  verdict: Verdict
  width?: number
  height?: number
  className?: string
}

/** Tiny readiness trend line (fixed 0..100 scale so groups are comparable). */
export function Sparkline({ values, verdict, width = 120, height = 32, className }: SparklineProps) {
  const label = `Readiness trend: ${values.map((v) => `${Math.floor(v)}%`).join(', ')}`
  const pad = 3
  const clamp = (v: number) => Math.min(100, Math.max(0, v))
  const x = (i: number) => (values.length <= 1 ? width / 2 : pad + (i * (width - pad * 2)) / (values.length - 1))
  const y = (v: number) => pad + ((100 - clamp(v)) * (height - pad * 2)) / 100
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const last = values[values.length - 1]
  const tone = verdict === 'ready' ? 'text-pass' : 'text-fail'

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={cn('shrink-0 overflow-visible', className)}
    >
      <title>{label}</title>
      <line x1={pad} x2={width - pad} y1={y(100)} y2={y(100)} className="stroke-border" strokeDasharray="2 3" strokeWidth={1} />
      <line x1={pad} x2={width - pad} y1={y(0)} y2={y(0)} className="stroke-border" strokeWidth={1} />
      {values.length > 1 && (
        <polyline points={points} fill="none" className="stroke-fg-muted" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      )}
      {last !== undefined && <circle cx={x(values.length - 1)} cy={y(last)} r={3} className={cn('fill-current', tone)} />}
    </svg>
  )
}
