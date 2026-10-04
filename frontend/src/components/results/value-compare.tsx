import { TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { Location, TextDiff, ValueSnapshot } from '@/lib/types'
import { DiffView } from './diff/diff-view'

export interface ValueCompareProps {
  expected: ValueSnapshot | null
  actual: ValueSnapshot | null
  /** Char diff of two strings (Evidence.value_diff). */
  valueDiff?: TextDiff | null
  /** Shown instead of the received value when there is none (exception, timeout...). */
  missingActualText?: string
  onOpenSource?: (location: Location) => void
  className?: string
}

function TypePill({ type, tone }: { type: string; tone: 'neutral' | 'expected' | 'mismatch' }) {
  return (
    <span
      className={cn(
        'inline-flex h-5 shrink-0 items-center rounded-md border px-1.5 font-mono text-2xs font-medium',
        tone === 'neutral' && 'border-border-strong bg-surface-2 text-fg-muted',
        tone === 'expected' && 'border-pass/30 bg-pass/10 text-pass',
        tone === 'mismatch' && 'border-fail/30 bg-fail/10 text-fail',
      )}
    >
      {type}
    </span>
  )
}

function ValueRow({
  label,
  snapshot,
  pillTone,
  valueClass,
  placeholder,
}: {
  label: string
  snapshot: ValueSnapshot | null
  pillTone: 'neutral' | 'expected' | 'mismatch'
  valueClass?: string
  placeholder?: string
}) {
  return (
    <div className="grid grid-cols-[5rem_minmax(0,1fr)] items-center gap-3 px-3 py-2">
      <dt className="text-2xs font-semibold tracking-wider text-fg-subtle uppercase">{label}</dt>
      <dd className="flex min-w-0 items-center gap-2">
        {snapshot ? (
          <>
            <code className={cn('min-w-0 overflow-x-auto font-mono text-sm whitespace-pre text-fg', valueClass)}>
              {snapshot.repr}
            </code>
            <TypePill type={snapshot.type} tone={pillTone} />
          </>
        ) : (
          <span className="text-sm text-fg-subtle italic">{placeholder ?? 'No value'}</span>
        )}
      </dd>
    </div>
  )
}

/** Expected vs received return value, with type pills that turn red when the types differ. */
export function ValueCompare({ expected, actual, valueDiff, missingActualText, onOpenSource, className }: ValueCompareProps) {
  const typeMismatch = Boolean(expected && actual && expected.type !== actual.type)
  const valueMismatch = Boolean(expected && actual && expected.repr !== actual.repr)

  return (
    <div className={cn('space-y-2', className)}>
      <dl className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-code-bg">
        <ValueRow label="Expected" snapshot={expected} pillTone={typeMismatch ? 'expected' : 'neutral'} />
        <ValueRow
          label="Received"
          snapshot={actual}
          pillTone={typeMismatch ? 'mismatch' : 'neutral'}
          valueClass={valueMismatch ? 'text-fail' : undefined}
          placeholder={missingActualText}
        />
      </dl>
      {typeMismatch && expected && actual && (
        <p className="flex items-start gap-1.5 text-xs text-fail" role="note">
          <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
          <span>
            Type mismatch: expected <code className="font-mono">{expected.type}</code>, received{' '}
            <code className="font-mono">{actual.type}</code>
            {expected.repr === actual.repr.replace(/^['"]|['"]$/g, '') && ' (same text, but quoted: it is a string)'}.
          </span>
        </p>
      )}
      {valueDiff && !valueDiff.equal && (
        <DiffView diff={valueDiff} title="Character difference" onOpenSource={onOpenSource} />
      )}
    </div>
  )
}
