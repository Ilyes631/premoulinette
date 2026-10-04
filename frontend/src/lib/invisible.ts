/**
 * Invisible-character rendering for diffs. Mirrors compare/text_diff.py `visible()`:
 * ' ' → '·', '\t' → '→', '\n' → '↵' (+ real newline), '\r' → '␍'.
 * Every replacement is exactly one character, so caret rows stay aligned in monospace.
 */

export const INVISIBLE_GLYPHS: Readonly<Record<string, string>> = {
  ' ': '·',
  '\t': '→',
  '\r': '␍',
  '\n': '↵',
  ' ': '⍽', // non-breaking space: a classic invisible typo
}

/** Glyph shown at the end of a line for its terminator ("" = no terminator). */
export function eolGlyph(eol: string): string {
  if (eol === '\r\n') return '␍↵'
  if (eol === '\n') return '↵'
  if (eol === '\r') return '␍'
  return ''
}

/** Backend-compatible string conversion (keeps a real newline after '↵'). */
export function toVisible(text: string): string {
  let out = ''
  for (const ch of text) {
    if (ch === '\n') out += '↵\n'
    else out += INVISIBLE_GLYPHS[ch] ?? ch
  }
  return out
}

export function isInvisible(ch: string): boolean {
  return ch in INVISIBLE_GLYPHS
}

/** Index where the trailing run of spaces/tabs starts (text.length when there is none). */
export function trailingWhitespaceStart(text: string): number {
  let i = text.length
  while (i > 0) {
    const ch = text[i - 1]
    if (ch !== ' ' && ch !== '\t' && ch !== ' ') break
    i -= 1
  }
  return i
}

export type VisiblePartKind = 'text' | 'invisible' | 'trailing'

export interface VisiblePart {
  /** Text to render (glyphs substituted when invisibles are shown). */
  text: string
  /** Original characters. */
  raw: string
  kind: VisiblePartKind
}

/**
 * Splits a single line (no terminator) into renderable parts.
 * - `trailing`: the trailing whitespace run, always flagged (subtle highlight even when hidden).
 * - `invisible`: other whitespace, only distinguished when `show` is true.
 * `offset` lets callers pass a slice of a longer line: trailing detection uses `lineEnd`.
 */
export function splitVisible(
  text: string,
  show: boolean,
  options: { offset?: number; trailingFrom?: number } = {},
): VisiblePart[] {
  const offset = options.offset ?? 0
  const trailingFrom = options.trailingFrom ?? offset + trailingWhitespaceStart(text)
  const parts: VisiblePart[] = []
  let current: VisiblePart | null = null

  const push = (raw: string, kind: VisiblePartKind) => {
    const rendered = show && kind !== 'text' ? (INVISIBLE_GLYPHS[raw] ?? raw) : raw
    if (current && current.kind === kind) {
      current.text += rendered
      current.raw += raw
    } else {
      current = { text: rendered, raw, kind }
      parts.push(current)
    }
  }

  let index = offset
  for (const ch of text) {
    if (index >= trailingFrom && (ch === ' ' || ch === '\t' || ch === ' ')) push(ch, 'trailing')
    else if (show && isInvisible(ch)) push(ch, 'invisible')
    else push(ch, 'text')
    index += ch.length
  }
  return parts
}
