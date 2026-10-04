/**
 * Pure helpers behind <DiffView>: per-side spans from char segments, caret rows and
 * collapsing of long runs of identical lines. Kept free of React so they are unit-testable.
 */
import { eolGlyph } from './invisible'
import type { DiffLine, DiffSegment } from './types'

export interface SideSpan {
  /** Original characters of this side ("" for an insertion point). */
  text: string
  /** Differs from the other side. */
  marked: boolean
  /** Zero-width position where the other side has extra text. */
  point?: boolean
  /** Line terminator glyph span ("↵"). */
  eol?: boolean
}

export type DiffSide = 'expected' | 'actual'

/** Segments of a changed line; falls back to a whole-line replacement when none are provided. */
export function lineSegments(line: DiffLine): DiffSegment[] {
  if (line.segments.length) return line.segments
  return [{ op: 'replace', expected: line.expected ?? '', actual: line.actual ?? '' }]
}

/** Spans of one side of a changed line (text + EOL marker). */
export function sideSpans(line: DiffLine, side: DiffSide): SideSpan[] {
  const spans: SideSpan[] = []
  for (const seg of lineSegments(line)) {
    const text = side === 'expected' ? seg.expected : seg.actual
    if (seg.op === 'equal') {
      spans.push({ text, marked: false })
    } else if (text) {
      spans.push({ text, marked: true })
    } else {
      // Present only on the other side: zero-width marker here.
      spans.push({ text: '', marked: true, point: true })
    }
  }
  const eol = side === 'expected' ? line.expected_eol : line.actual_eol
  const otherEol = side === 'expected' ? line.actual_eol : line.expected_eol
  if (eol !== otherEol) {
    spans.push(eol ? { text: eolGlyph(eol), marked: true, eol: true } : { text: '', marked: true, point: true, eol: true })
  }
  return spans
}

const WIDE_RE =
  /[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]|\p{Extended_Pictographic}/u

/** A character whose monospace cell can safely be replaced by '^' or ' '. */
export function isSimpleCell(ch: string): boolean {
  return ch.length === 1 && ch !== '\t' && ch !== '\r' && ch !== '\n' && !WIDE_RE.test(ch)
}

export type CaretCellKind = 'space' | 'caret' | 'ghost' | 'ghost-mark' | 'point'

export interface CaretCell {
  kind: CaretCellKind
  /** Text occupying the cell: ' ' / '^' or the original (rendered) char for ghosts. */
  text: string
}

/**
 * Cells of the marker row drawn under a side. `render` maps original text to what is displayed
 * (glyph substitution for invisibles) so widths match the row above exactly.
 * - simple unmarked char → space; simple marked char → '^'
 * - complex char (tab, emoji...) → transparent copy ("ghost"), underlined when marked
 * - insertion point → zero-width '^' anchor
 */
export function caretCells(spans: SideSpan[], render: (text: string) => string = (t) => t): CaretCell[] {
  const cells: CaretCell[] = []
  const push = (kind: CaretCellKind, text: string) => {
    const last = cells[cells.length - 1]
    if (last && last.kind === kind && kind !== 'point') last.text += text
    else cells.push({ kind, text })
  }
  for (const span of spans) {
    if (span.point) {
      push('point', '^')
      continue
    }
    for (const ch of render(span.text)) {
      if (isSimpleCell(ch)) push(span.marked ? 'caret' : 'space', span.marked ? '^' : ' ')
      else push(span.marked ? 'ghost-mark' : 'ghost', ch)
    }
  }
  // Trailing spaces carry no information.
  while (cells.length && cells[cells.length - 1]?.kind === 'space') cells.pop()
  return cells
}

/** Plain-text caret line (ghost cells as spaces), e.g. "               ^". Used for a11y and tests. */
export function caretLine(spans: SideSpan[], render?: (text: string) => string): string {
  return caretCells(spans, render)
    .map((c) => (c.kind === 'caret' || c.kind === 'point' ? c.text : c.kind === 'ghost-mark' ? '^'.repeat(Array.from(c.text).length) : ' '.repeat(Array.from(c.text).length)))
    .join('')
    .replace(/\s+$/, '')
}

export type DiffItem =
  | { type: 'line'; index: number; line: DiffLine }
  | { type: 'gap'; key: string; from: number; to: number; lines: DiffLine[] }

/**
 * Collapses runs of identical lines longer than `2 * context + minHidden`, keeping `context`
 * lines around every difference. `expanded` holds gap keys the user chose to reveal.
 */
export function collapseEqualRuns(
  lines: DiffLine[],
  context = 2,
  minHidden = 3,
  expanded: ReadonlySet<string> = new Set(),
): DiffItem[] {
  const items: DiffItem[] = []
  let i = 0
  while (i < lines.length) {
    if (lines[i]?.op !== 'equal') {
      items.push({ type: 'line', index: i, line: lines[i] as DiffLine })
      i += 1
      continue
    }
    let end = i
    while (end < lines.length && lines[end]?.op === 'equal') end += 1
    const head = i === 0 ? 0 : context
    const tail = end === lines.length ? 0 : context
    const hiddenFrom = i + head
    const hiddenTo = end - tail
    const key = `${hiddenFrom}-${hiddenTo}`
    const collapsible = hiddenTo - hiddenFrom >= minHidden && !expanded.has(key)
    for (let k = i; k < end; k += 1) {
      if (collapsible && k === hiddenFrom) {
        items.push({ type: 'gap', key, from: hiddenFrom, to: hiddenTo, lines: lines.slice(hiddenFrom, hiddenTo) })
        k = hiddenTo - 1
        continue
      }
      items.push({ type: 'line', index: k, line: lines[k] as DiffLine })
    }
    i = end
  }
  return items
}
