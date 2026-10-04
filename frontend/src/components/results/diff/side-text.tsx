import { caretCells, type DiffSide, type SideSpan } from '@/lib/diff'
import { cn } from '@/lib/cn'
import { INVISIBLE_GLYPHS, trailingWhitespaceStart } from '@/lib/invisible'
import { VisibleText } from './visible-text'

const MARK_CLASS: Record<DiffSide, string> = {
  expected: 'rounded-[2px] bg-fail/25 text-fail',
  actual: 'rounded-[2px] bg-pass/25 text-pass',
}

const POINT_CLASS: Record<DiffSide, string> = {
  expected: 'bg-fail',
  actual: 'bg-pass',
}

export interface SideTextProps {
  spans: SideSpan[]
  side: DiffSide
  show: boolean
  /** Full line text of this side, for trailing whitespace detection. */
  lineText: string
}

/** One side (expected or received) of a changed line, with per-character marks. */
export function SideText({ spans, side, show, lineText }: SideTextProps) {
  const trailingFrom = trailingWhitespaceStart(lineText)
  let offset = 0
  return (
    <>
      {spans.map((span, i) => {
        if (span.point) {
          return (
            <span
              key={i}
              data-op="point"
              className="relative inline-block w-0 align-baseline"
              title={side === 'actual' ? 'Missing here' : 'Unexpected text here'}
            >
              <span aria-hidden className={cn('absolute -top-[0.1em] -left-px h-[1.15em] w-0.5 rounded-full', POINT_CLASS[side])} />
            </span>
          )
        }
        if (span.eol) {
          return (
            <span key={i} data-op="eol" className={cn(span.marked && MARK_CLASS[side])} title="Line terminator">
              {span.text}
            </span>
          )
        }
        const start = offset
        offset += span.text.length
        return (
          <span key={i} data-op={span.marked ? (side === 'expected' ? 'delete' : 'insert') : 'equal'} className={cn(span.marked && MARK_CLASS[side])}>
            <VisibleText text={span.text} show={show || span.marked} offset={start} trailingFrom={trailingFrom} />
          </span>
        )
      })}
    </>
  )
}

/** Same glyph substitution as VisibleText, used to keep the caret row aligned. */
export function renderForCaret(show: boolean) {
  return (text: string) =>
    show ? Array.from(text, (ch) => (ch === '\n' ? ch : (INVISIBLE_GLYPHS[ch] ?? ch))).join('') : text
}

/** Marker row ("^^^") aligned under the differing characters of a side. */
export function CaretRow({ spans, show, side }: { spans: SideSpan[]; show: boolean; side: DiffSide }) {
  // Marked spans always render their invisibles as glyphs (see SideText), so mirror that here.
  const render = (span: SideSpan) => renderForCaret(show || span.marked)(span.text)
  const cells = caretCells(
    spans.map((s) => ({ ...s, text: s.point || s.eol ? s.text : render(s) })),
  )
  const color = side === 'actual' ? 'text-pass' : 'text-fail'
  return (
    <span aria-hidden data-caret-row className={cn('select-none', color)}>
      {cells.map((cell, i) => {
        switch (cell.kind) {
          case 'space':
            return cell.text
          case 'caret':
            return (
              <span key={i} data-caret className="font-bold">
                {cell.text}
              </span>
            )
          case 'point':
            return (
              <span key={i} data-caret className="relative inline-block w-0">
                <span className="absolute left-0 -translate-x-1/2 font-bold">^</span>
              </span>
            )
          case 'ghost':
            return (
              <span key={i} className="text-transparent">
                {cell.text}
              </span>
            )
          case 'ghost-mark':
            return (
              <span key={i} data-caret className="border-b-2 border-current text-transparent">
                {cell.text}
              </span>
            )
        }
      })}
    </span>
  )
}
