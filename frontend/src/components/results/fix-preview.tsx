import { WandSparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/cn'
import { parseUnifiedDiff, type PatchLine } from '@/lib/patch'
import type { Fix } from '@/lib/types'

const CONFIDENCE_TONE = { high: 'pass', medium: 'warning', low: 'neutral' } as const

const LINE_CLASS: Record<PatchLine['kind'], string> = {
  file: 'text-fg-subtle',
  hunk: 'bg-info/10 text-info',
  add: 'bg-pass/10 text-fg',
  del: 'bg-fail/10 text-fg',
  context: 'text-fg-muted',
  meta: 'text-fg-subtle italic',
}

const SIGN: Partial<Record<PatchLine['kind'], string>> = { add: '+', del: '-', context: ' ' }

function PatchView({ lines }: { lines: PatchLine[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-code-bg">
      <pre className="w-max min-w-full py-1.5 font-mono text-[0.8125rem] leading-6">
        {lines.map((line, i) => (
          <div key={i} className={cn('flex pr-4', LINE_CLASS[line.kind])} data-kind={line.kind}>
            <span className="w-10 shrink-0 pr-2 text-right text-fg-subtle/70 tabular select-none" aria-hidden>
              {line.kind === 'del' ? line.oldNo : line.kind === 'add' || line.kind === 'context' ? line.newNo : ''}
            </span>
            <span
              className={cn(
                'w-4 shrink-0 select-none',
                line.kind === 'add' && 'text-pass',
                line.kind === 'del' && 'text-fail',
              )}
              aria-hidden
            >
              {SIGN[line.kind] ?? ''}
            </span>
            <span className="whitespace-pre">
              {line.kind === 'add' && <span className="sr-only">Added: </span>}
              {line.kind === 'del' && <span className="sr-only">Removed: </span>}
              {line.text || ' '}
            </span>
          </div>
        ))}
      </pre>
    </div>
  )
}

/** Minimal suggested change (never applied automatically): before/after or a unified patch. */
export function FixPreview({ fix, className }: { fix: Fix; className?: string }) {
  const patchLines = fix.patch ? parseUnifiedDiff(fix.patch) : null
  const beforeAfter: PatchLine[] | null =
    !patchLines && (fix.before !== null || fix.after !== null)
      ? [
          ...(fix.before !== null ? [{ kind: 'del' as const, text: fix.before, oldNo: null, newNo: null }] : []),
          ...(fix.after !== null ? [{ kind: 'add' as const, text: fix.after, oldNo: null, newNo: null }] : []),
        ]
      : null
  return (
    <section aria-label="Suggested fix" className={cn('space-y-2', className)}>
      <div className="flex flex-wrap items-center gap-2">
        <WandSparkles className="size-4 text-accent-fg" aria-hidden />
        <h3 className="text-sm font-semibold text-fg">Suggested fix</h3>
        <Badge tone={CONFIDENCE_TONE[fix.confidence]} variant="outline">
          {fix.confidence} confidence
        </Badge>
        {fix.file && <span className="font-mono text-2xs text-fg-subtle">{fix.file}</span>}
      </div>
      <p className="text-sm text-fg-muted">{fix.summary}</p>
      {patchLines && <PatchView lines={patchLines} />}
      {beforeAfter && <PatchView lines={beforeAfter} />}
      <p className="text-2xs text-fg-subtle">Suggestions are never applied automatically. Review before editing your code.</p>
    </section>
  )
}
