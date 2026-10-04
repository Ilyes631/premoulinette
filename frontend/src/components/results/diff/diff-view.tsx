import { ChevronsUpDown, CircleCheck, GitCompareArrows } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/cn'
import { collapseEqualRuns } from '@/lib/diff'
import type { DiffKind, Location, TextDiff } from '@/lib/types'
import { ChangedBlock, EqualRow, type RowLabels } from './diff-rows'

const KIND_LABELS: Partial<Record<DiffKind, string>> = {
  typo: 'Typo',
  case: 'Case',
  whitespace: 'Whitespace',
  trailing_whitespace: 'Trailing space',
  missing_newline: 'Missing newline',
  extra_newline: 'Extra newline',
  crlf: 'CRLF line endings',
  missing_lines: 'Missing lines',
  extra_lines: 'Extra lines',
  different: 'Different text',
}

export interface DiffViewProps {
  diff: TextDiff
  /** Called when a "line 31" source chip is clicked. */
  onOpenSource?: (location: Location) => void
  title?: ReactNode
  labels?: Partial<RowLabels>
  defaultShowInvisibles?: boolean
  /** Identical lines kept around each difference before collapsing. */
  contextLines?: number
  className?: string
}

export function DiffView({
  diff,
  onOpenSource,
  title,
  labels,
  defaultShowInvisibles = false,
  contextLines = 2,
  className,
}: DiffViewProps) {
  const [show, setShow] = useState(defaultShowInvisibles)
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set())
  const rowLabels: RowLabels = { expected: 'Expected', actual: 'Received', ...labels }
  const items = useMemo(
    () => collapseEqualRuns(diff.lines, contextLines, 3, expanded),
    [diff.lines, contextLines, expanded],
  )
  const kinds = diff.kinds.filter((k) => k !== 'identical')

  return (
    <section
      aria-label={typeof title === 'string' ? title : 'Output difference'}
      className={cn('overflow-hidden rounded-lg border border-border bg-code-bg', className)}
    >
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border bg-surface-2/50 px-3 py-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {diff.equal ? (
            <CircleCheck className="size-4 shrink-0 text-pass" aria-hidden />
          ) : (
            <GitCompareArrows className="size-4 shrink-0 text-fg-subtle" aria-hidden />
          )}
          <div className="min-w-0">
            {title && <div className="text-xs font-semibold text-fg">{title}</div>}
            <p className="text-xs text-pretty text-fg-muted" data-testid="diff-summary">
              {diff.summary || (diff.equal ? 'Outputs are identical.' : 'Outputs differ.')}
            </p>
          </div>
        </div>
        {kinds.length > 0 && (
          <ul className="flex flex-wrap gap-1" aria-label="Kinds of difference">
            {kinds.map((kind) => (
              <li key={kind} className="rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium text-fg-muted">
                {KIND_LABELS[kind] ?? kind}
              </li>
            ))}
          </ul>
        )}
        <Switch size="sm" checked={show} onCheckedChange={setShow} label="Show invisible characters" />
      </header>

      {diff.lines.length === 0 ? (
        <p className="px-3 py-4 text-xs text-fg-subtle italic">{diff.equal ? 'Nothing to show.' : 'Both outputs are empty.'}</p>
      ) : (
        <div className="overflow-x-auto">
          <div className="w-max min-w-full py-1 font-mono text-[0.8125rem] leading-6" role="list">
            {items.map((item) => {
              if (item.type === 'gap') {
                return (
                  <button
                    key={`gap-${item.key}`}
                    type="button"
                    role="listitem"
                    onClick={() => setExpanded((prev) => new Set(prev).add(item.key))}
                    className="sticky left-0 flex w-full items-center gap-2 py-1 pl-3 font-sans text-xs text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg"
                  >
                    <ChevronsUpDown className="size-3.5" aria-hidden />
                    Show {item.lines.length} matching lines
                  </button>
                )
              }
              const { line, index } = item
              return (
                <div role="listitem" key={index}>
                  {line.op === 'equal' ? (
                    <EqualRow line={line} show={show} />
                  ) : (
                    <ChangedBlock line={line} show={show} labels={rowLabels} onOpenSource={onOpenSource} />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}
