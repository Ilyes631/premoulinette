import type { Location } from './types'

/** "87%" — scores are 0..100 floats; never shows "100%" unless it really is 100. */
export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const factor = 10 ** digits
  const floored = Math.floor(value * factor) / factor
  return `${floored.toFixed(digits)}%`
}

/** Normalizes 0..1 or 0..100 progress values to 0..100. */
export function toPercent(progress: number | null | undefined): number {
  if (progress === null || progress === undefined || Number.isNaN(progress)) return 0
  const value = progress <= 1 ? progress * 100 : progress
  return Math.min(100, Math.max(0, value))
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.floor(seconds % 60)
  return `${minutes} min ${String(rest).padStart(2, '0')} s`
}

/** "00:07" style elapsed timer. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const RELATIVE_UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

export function formatRelativeTime(iso: string | Date, now: Date = new Date()): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso
  if (Number.isNaN(date.getTime())) return ''
  const deltaSeconds = (date.getTime() - now.getTime()) / 1000
  const abs = Math.abs(deltaSeconds)
  if (abs < 45) return 'just now'
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  for (const [unit, seconds] of RELATIVE_UNITS) {
    if (abs >= seconds || unit === 'minute') {
      return rtf.format(Math.round(deltaSeconds / seconds), unit)
    }
  }
  return ''
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`
}

export function basename(path: string): string {
  const clean = path.replace(/\/+$/, '')
  return clean.slice(clean.lastIndexOf('/') + 1) || clean
}

/** "kelvin.py:31" (or the full path with `full`). */
export function formatLocation(loc: Pick<Location, 'file' | 'line'>, full = false): string {
  const file = full ? loc.file : basename(loc.file)
  return loc.line ? `${file}:${loc.line}` : file
}
