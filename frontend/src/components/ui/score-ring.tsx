import { animate, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'

export type ScoreTone = 'pass' | 'warning' | 'fail' | 'accent' | 'bonus' | 'neutral'

const STROKE: Record<ScoreTone, string> = {
  pass: 'stroke-pass',
  warning: 'stroke-warning',
  fail: 'stroke-fail',
  accent: 'stroke-accent',
  bonus: 'stroke-bonus',
  neutral: 'stroke-fg-subtle',
}

/** Default color scale for readiness percentages. */
export function scoreTone(value: number | null | undefined): ScoreTone {
  if (value === null || value === undefined) return 'neutral'
  if (value >= 100) return 'pass'
  if (value >= 70) return 'warning'
  return 'fail'
}

/** Animated integer count-up (instant when the user prefers reduced motion). */
export function useCountUp(target: number, durationS = 0.8): number {
  const reduce = useReducedMotion()
  const [display, setDisplay] = useState(reduce ? target : 0)
  useEffect(() => {
    if (reduce) {
      setDisplay(target)
      return
    }
    const controls = animate(0, target, {
      duration: durationS,
      ease: [0.25, 1, 0.5, 1],
      onUpdate: (v) => setDisplay(v),
    })
    return () => controls.stop()
  }, [target, durationS, reduce])
  return display
}

export interface ScoreRingProps {
  /** 0..100, null = not computable. */
  value: number | null
  size?: number
  stroke?: number
  tone?: ScoreTone
  /** Small caption under the number ("ready"). */
  caption?: string
  /** Accessible name, e.g. "Mandatory readiness". */
  label: string
  className?: string
}

export function ScoreRing({ value, size = 128, stroke = 10, tone, caption, label, className }: ScoreRingProps) {
  const reduce = useReducedMotion()
  const safe = value === null ? 0 : Math.min(100, Math.max(0, value))
  const shown = useCountUp(Math.floor(safe))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const target = circumference * (1 - safe / 100)
  const resolvedTone = tone ?? scoreTone(value)
  const big = size >= 96

  return (
    <div
      role="img"
      aria-label={`${label}: ${value === null ? 'not available' : `${Math.floor(safe)}%`}`}
      className={cn('relative inline-flex shrink-0 items-center justify-center', className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-fg/10" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          className={STROKE[resolvedTone]}
          initial={{ strokeDashoffset: reduce ? target : circumference }}
          animate={{ strokeDashoffset: target }}
          transition={{ duration: reduce ? 0 : 0.9, ease: [0.25, 1, 0.5, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden>
        <span
          className={cn(
            'tabular font-semibold tracking-tight text-fg',
            big ? 'text-3xl' : size >= 56 ? 'text-base' : 'text-xs',
          )}
        >
          {value === null ? '—' : Math.round(shown)}
          {value !== null && <span className={cn('text-fg-muted', big ? 'text-base' : 'text-[0.7em]')}>%</span>}
        </span>
        {caption && big && <span className="mt-0.5 text-2xs font-medium uppercase tracking-wider text-fg-subtle">{caption}</span>}
      </div>
    </div>
  )
}
