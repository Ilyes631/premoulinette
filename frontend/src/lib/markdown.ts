/**
 * Tiny, safe Markdown parser for explanations (template or AI generated).
 * It produces a plain AST rendered with React elements — raw HTML is NEVER interpreted:
 * "<script>" stays literal text. Supported: paragraphs, headings, bold, italics, inline code,
 * fenced code blocks, ordered/unordered lists, blockquotes, horizontal rules and http(s) links.
 */

export type MdInline =
  | { type: 'text'; text: string }
  | { type: 'strong'; children: MdInline[] }
  | { type: 'em'; children: MdInline[] }
  | { type: 'code'; text: string }
  | { type: 'link'; href: string; children: MdInline[] }

export type MdBlock =
  | { type: 'paragraph'; children: MdInline[] }
  | { type: 'heading'; level: number; children: MdInline[] }
  | { type: 'code'; lang: string | null; text: string }
  | { type: 'list'; ordered: boolean; start: number; items: MdInline[][] }
  | { type: 'quote'; children: MdInline[] }
  | { type: 'hr' }

const FENCE_RE = /^\s*(`{3,}|~{3,})\s*([\w+#.-]*)\s*$/
const HEADING_RE = /^(#{1,6})\s+(.*?)\s*#*\s*$/
const HR_RE = /^\s*(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/
const UL_RE = /^\s*[-*+]\s+(.*)$/
const OL_RE = /^\s*(\d{1,9})[.)]\s+(.*)$/
const QUOTE_RE = /^\s*>\s?(.*)$/
const ESCAPABLE = /[\\`*_[\]()#+\-.!>~|{}]/
const SAFE_HREF = /^(?:https?:\/\/|mailto:)/i

export function isSafeHref(href: string): boolean {
  return SAFE_HREF.test(href.trim())
}

const isWordChar = (ch: string | undefined) => ch !== undefined && /[\p{L}\p{N}_]/u.test(ch)

/** Parses inline markup of a single paragraph / list item. */
export function parseInline(src: string): MdInline[] {
  const out: MdInline[] = []
  let buffer = ''
  const flush = () => {
    if (buffer) out.push({ type: 'text', text: buffer })
    buffer = ''
  }

  let i = 0
  while (i < src.length) {
    const ch = src[i] as string

    if (ch === '\\' && i + 1 < src.length && ESCAPABLE.test(src[i + 1] as string)) {
      buffer += src[i + 1]
      i += 2
      continue
    }

    if (ch === '`') {
      const run = /^`+/.exec(src.slice(i))?.[0] ?? '`'
      const close = src.indexOf(run, i + run.length)
      if (close !== -1) {
        let code = src.slice(i + run.length, close)
        if (code.length > 1 && code.startsWith(' ') && code.endsWith(' ')) code = code.slice(1, -1)
        flush()
        out.push({ type: 'code', text: code })
        i = close + run.length
        continue
      }
      buffer += run
      i += run.length
      continue
    }

    const pair = src.slice(i, i + 2)
    if (pair === '**' || pair === '__') {
      const close = src.indexOf(pair, i + 2)
      if (close > i + 2 && (pair === '**' || !isWordChar(src[close + 2]))) {
        flush()
        out.push({ type: 'strong', children: parseInline(src.slice(i + 2, close)) })
        i = close + 2
        continue
      }
    }

    if ((ch === '*' || ch === '_') && src[i + 1] !== ch && src[i + 1] !== ' ') {
      const opensWord = ch === '*' || !isWordChar(src[i - 1])
      if (opensWord) {
        let close = i + 1
        while ((close = src.indexOf(ch, close)) !== -1) {
          const valid = src[close - 1] !== ' ' && (ch === '*' || !isWordChar(src[close + 1]))
          if (valid && src[close + 1] !== ch) break
          close += 1
        }
        if (close !== -1 && close > i + 1) {
          flush()
          out.push({ type: 'em', children: parseInline(src.slice(i + 1, close)) })
          i = close + 1
          continue
        }
      }
    }

    if (ch === '[') {
      const link = /^\[([^\]\n]+)\]\(([^)\s]+)\)/.exec(src.slice(i))
      if (link) {
        const [whole, label = '', href = ''] = link
        flush()
        if (isSafeHref(href)) out.push({ type: 'link', href, children: parseInline(label) })
        else out.push(...parseInline(label))
        i += whole.length
        continue
      }
    }

    buffer += ch
    i += 1
  }
  flush()
  return out
}

/** Parses a Markdown document into blocks. */
export function parseMarkdown(src: string): MdBlock[] {
  const lines = src.replace(/\r\n?/g, '\n').split('\n')
  const blocks: MdBlock[] = []
  let paragraph: string[] = []
  let list: { ordered: boolean; start: number; items: string[] } | null = null
  let quote: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', children: parseInline(paragraph.join(' ')) })
    paragraph = []
  }
  const flushList = () => {
    if (list) blocks.push({ type: 'list', ordered: list.ordered, start: list.start, items: list.items.map(parseInline) })
    list = null
  }
  const flushQuote = () => {
    if (quote.length) blocks.push({ type: 'quote', children: parseInline(quote.join(' ')) })
    quote = []
  }
  const flushAll = () => {
    flushParagraph()
    flushList()
    flushQuote()
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] as string

    const fence = FENCE_RE.exec(line)
    if (fence) {
      flushAll()
      const marker = fence[1] as string
      const body: string[] = []
      i += 1
      while (i < lines.length && !(lines[i] as string).trim().startsWith(marker)) {
        body.push(lines[i] as string)
        i += 1
      }
      blocks.push({ type: 'code', lang: fence[2] || null, text: body.join('\n') })
      continue
    }

    if (!line.trim()) {
      flushAll()
      continue
    }

    const heading = HEADING_RE.exec(line)
    if (heading) {
      flushAll()
      blocks.push({ type: 'heading', level: (heading[1] as string).length, children: parseInline(heading[2] ?? '') })
      continue
    }

    if (HR_RE.test(line)) {
      flushAll()
      blocks.push({ type: 'hr' })
      continue
    }

    const ul = UL_RE.exec(line)
    const ol = ul ? null : OL_RE.exec(line)
    if (ul || ol) {
      flushParagraph()
      flushQuote()
      const ordered = Boolean(ol)
      if (list && list.ordered !== ordered) flushList()
      if (!list) list = { ordered, start: ol ? Number(ol[1]) : 1, items: [] }
      list.items.push((ul ? ul[1] : ol?.[2]) ?? '')
      continue
    }

    const q = QUOTE_RE.exec(line)
    if (q) {
      flushParagraph()
      flushList()
      quote.push(q[1] ?? '')
      continue
    }

    if (list && /^\s+\S/.test(line)) {
      const items: string[] = (list as { items: string[] }).items
      items[items.length - 1] += ` ${line.trim()}`
      continue
    }

    flushList()
    flushQuote()
    paragraph.push(line.trim())
  }
  flushAll()
  return blocks
}
