import { useEffect, useState } from 'react'

/** Parses backend ISO datetimes (Python may emit microseconds, which some engines reject). */
export function parseServerDate(iso: string | null | undefined): number | null {
  if (!iso) return null
  const normalized = iso.replace(/(\.\d{3})\d+/, '$1')
  const t = Date.parse(normalized)
  return Number.isNaN(t) ? null : t
}

/** Milliseconds elapsed since `startIso` (or mount), frozen at `endIso` once the job finished. */
export function useElapsed(startIso: string | null | undefined, endIso: string | null | undefined, running: boolean): number {
  const [mountedAt] = useState(() => Date.now())
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(timer)
  }, [running])

  const start = parseServerDate(startIso) ?? mountedAt
  // Clocks are the same machine, but never show a negative or absurd value.
  const end = parseServerDate(endIso) ?? now
  return Math.max(0, end - Math.min(start, end))
}
