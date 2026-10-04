import { cn } from '@/lib/cn'

interface SparklineProps {
  /** Readiness values (0..100), oldest first. */
  values: number[]
  /** Index of the highlighted point (current analysis). */
  current?: number
  width?: number
  height?: number
  className?: string
}

/** Tiny readiness trend line. Scale is fixed to 0..100 so trends are comparable. */
export function Sparkline({ values, current, width = 160, height = 40, className }: SparklineProps) {
  if (values.length === 0) return null
  const pad = 4
  const w = width - pad * 2
  const h = height - pad * 2
  const x = (i: number) => pad + (values.length === 1 ? w / 2 : (i * w) / (values.length - 1))
  const y = (v: number) => pad + h - (Math.min(100, Math.max(0, v)) / 100) * h
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const first = values[0] as number
  const last = values[values.length - 1] as number
  const highlighted = current !== undefined && current >= 0 && current < values.length ? current : values.length - 1
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Readiness over ${values.length} ${values.length === 1 ? 'analysis' : 'analyses'}: from ${first.toFixed(1)}% to ${last.toFixed(1)}%`}
      className={cn('overflow-visible', className)}
    >
      <line x1={pad} x2={width - pad} y1={y(100)} y2={y(100)} className="stroke-pass/30" strokeDasharray="2 3" />
      {values.length > 1 && (
        <polyline
          points={points}
          fill="none"
          strokeWidth={1.75}
          strokeLinejoin="round"
          strokeLinecap="round"
          className="stroke-accent-fg"
        />
      )}
      {values.map((v, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(v)}
          r={i === highlighted ? 3.5 : 2}
          className={i === highlighted ? 'fill-accent-fg stroke-surface' : 'fill-fg-subtle'}
          strokeWidth={i === highlighted ? 2 : 0}
        />
      ))}
    </svg>
  )
}
