import { CornerDownRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import { sideSpans } from '@/lib/diff'
import { eolGlyph } from '@/lib/invisible'
import type { DiffLine, Location } from '@/lib/types'
import { CaretRow, SideText } from './side-text'
import { VisibleText } from './visible-text'

export interface RowLabels {
  expected: string
  actual: string
}

/** Grid shared by every row: [label][line number][text]. */
const ROW = 'grid grid-cols-[4.75rem_2.75rem_minmax(0,1fr)] items-start'

function Gutter({ label, lineno, className }: { label?: string; lineno: number | null; className?: string }) {
  return (
    <>
      <span
        className={cn(
          'sticky left-0 z-[1] pl-3 font-sans text-2xs font-semibold tracking-wider uppercase select-none',
          className,
        )}
      >
        {label}
      </span>
      <span className="pr-3 text-right text-fg-subtle/80 tabular select-none" aria-hidden={!lineno}>
        {lineno ?? ''}
      </span>
    </>
  )
}

export function EqualRow({ line, show }: { line: DiffLine; show: boolean }) {
  const text = line.actual ?? line.expected ?? ''
  return (
    <div className={cn(ROW, 'bg-code-bg text-fg-muted')} data-line-op="equal">
      <Gutter lineno={line.actual_lineno ?? line.expected_lineno} className="bg-code-bg" />
      <span className="pr-4 whitespace-pre">
        <VisibleText text={text} show={show} />
        {show && <span className="text-fg-subtle/70">{eolGlyph(line.actual_eol)}</span>}
      </span>
    </div>
  )
}

export function SourceChip({ location, onOpenSource }: { location: Location; onOpenSource?: (loc: Location) => void }) {
  const label = location.line ? `line ${location.line}` : 'source'
  const full = `${location.file}${location.line ? `:${location.line}` : ''}`
  const className =
    'inline-flex h-5 items-center gap-1 rounded-md border border-border-strong bg-surface-2 px-1.5 font-mono text-2xs text-fg-muted'
  if (!onOpenSource) {
    return (
      <span className={className} title={full}>
        {label}
      </span>
    )
  }
  return (
    <Tooltip content={`Open ${full}`}>
      <button
        type="button"
        onClick={() => onOpenSource(location)}
        className={cn(className, 'transition-colors hover:border-accent-fg/50 hover:text-fg')}
        aria-label={`Open ${full}`}
      >
        <CornerDownRight className="size-3" aria-hidden />
        {label}
      </button>
    </Tooltip>
  )
}

function Placeholder({ children }: { children: ReactNode }) {
  return <span className="font-sans text-xs text-fg-subtle italic">{children}</span>
}

export interface ChangedBlockProps {
  line: DiffLine
  show: boolean
  labels: RowLabels
  onOpenSource?: (loc: Location) => void
}

/** A differing line: expected row, received row, caret row, then hints and source. */
export function ChangedBlock({ line, show, labels, onOpenSource }: ChangedBlockProps) {
  const hasExpected = line.op !== 'extra'
  const hasActual = line.op !== 'missing'
  const expSpans = line.op === 'changed' ? sideSpans(line, 'expected') : []
  const actSpans = line.op === 'changed' ? sideSpans(line, 'actual') : []

  return (
    <div
      data-line-op={line.op}
      className="relative border-y border-border bg-surface-2 py-1 shadow-[inset_2px_0_0_var(--pm-fail)] first:border-t-0 last:border-b-0"
    >
      <div className={cn(ROW, 'bg-transparent')} data-side="expected">
        <Gutter label={labels.expected} lineno={hasExpected ? line.expected_lineno : null} className="bg-surface-2 pt-px text-fail" />
        <span className="pr-4 whitespace-pre text-fg">
          {line.op === 'changed' && <SideText spans={expSpans} side="expected" show={show} lineText={line.expected ?? ''} />}
          {line.op === 'missing' && (
            <span data-op="delete" className="rounded-[2px] bg-fail/25 text-fail">
              <VisibleText text={line.expected ?? ''} show />
              {eolGlyph(line.expected_eol)}
            </span>
          )}
          {line.op === 'extra' && <Placeholder>no line expected here</Placeholder>}
        </span>
      </div>

      <div className={cn(ROW, 'bg-transparent')} data-side="actual">
        <Gutter label={labels.actual} lineno={hasActual ? line.actual_lineno : null} className="bg-surface-2 pt-px text-pass" />
        <span className="pr-4 whitespace-pre text-fg">
          {line.op === 'changed' && <SideText spans={actSpans} side="actual" show={show} lineText={line.actual ?? ''} />}
          {line.op === 'extra' && (
            <span data-op="insert" className="rounded-[2px] bg-pass/25 text-pass">
              <VisibleText text={line.actual ?? ''} show />
              {eolGlyph(line.actual_eol)}
            </span>
          )}
          {line.op === 'missing' && <Placeholder>line missing in your output</Placeholder>}
        </span>
      </div>

      {line.op === 'changed' && (
        <div className={ROW}>
          <span className="sticky left-0 bg-surface-2" />
          <span />
          <span className="pr-4 whitespace-pre">
            <CaretRow spans={actSpans} show={show} side="actual" />
          </span>
        </div>
      )}

      {(line.hints.length > 0 || line.source) && (
        <div className="sticky left-0 flex w-fit max-w-[calc(100vw-4rem)] flex-wrap items-center gap-1.5 py-1 pr-3 pl-[7.5rem] font-sans">
          {line.hints.map((hint) => (
            <span key={hint} className="rounded-md bg-warning/10 px-1.5 py-0.5 text-2xs font-medium text-warning">
              {hint}
            </span>
          ))}
          {line.source && (
            <span className="inline-flex items-center gap-1 text-2xs text-fg-subtle">
              printed by <SourceChip location={line.source} onOpenSource={onOpenSource} />
            </span>
          )}
        </div>
      )}
    </div>
  )
}
