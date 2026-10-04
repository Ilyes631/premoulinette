import { Quote } from 'lucide-react'
import { PROVENANCE_META } from '@/lib/check-meta'
import { cn } from '@/lib/cn'
import type { Origin } from '@/lib/types'

/** "Source: Explicit requirement · Confidence 100%" + the subject excerpt it comes from. */
export function ProvenanceLine({ origin, className }: { origin: Origin; className?: string }) {
  const meta = PROVENANCE_META[origin.provenance]
  const pct = Math.round(origin.confidence * 100)
  const unofficial = origin.provenance === 'heuristic'
  const review = origin.provenance === 'ai_extracted'
  return (
    <div className={cn('space-y-2', className)}>
      <p className="text-xs text-fg-muted">
        <span className="text-fg-subtle">Source:</span> <span className="font-medium text-fg">{meta.long}</span>
        <span className="text-fg-subtle"> · </span>
        Confidence <span className="tabular">{pct}%</span>
        {unofficial && <span className="text-fg-subtle"> · Not an official requirement</span>}
        {review && <span className="text-warning"> · Needs review</span>}
      </p>
      {origin.source?.excerpt && (
        <blockquote className="flex gap-2 rounded-md border border-border bg-surface-2/60 px-3 py-2 text-xs text-fg-muted">
          <Quote className="mt-0.5 size-3 shrink-0 text-fg-subtle" aria-hidden />
          <span className="min-w-0">
            <span className="font-mono break-words whitespace-pre-wrap text-fg">{origin.source.excerpt}</span>
            {(origin.source.section || origin.source.line) && (
              <span className="mt-1 block text-2xs text-fg-subtle">
                {origin.source.section}
                {origin.source.section && origin.source.line ? ' · ' : ''}
                {origin.source.line ? `subject line ${origin.source.line}` : ''}
              </span>
            )}
          </span>
        </blockquote>
      )}
      {origin.note && <p className="text-xs text-fg-subtle">{origin.note}</p>}
    </div>
  )
}
