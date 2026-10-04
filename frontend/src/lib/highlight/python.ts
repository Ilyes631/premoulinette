/**
 * Tiny, dependency-free Python tokenizer for display purposes only (never evaluates anything).
 * Handles keywords, builtins, constants, strings (prefixes, triple quotes spanning lines),
 * numbers, comments, decorators, def/class names, operators and punctuation.
 */

export type TokenKind =
  | 'keyword'
  | 'constant'
  | 'builtin'
  | 'string'
  | 'number'
  | 'comment'
  | 'function'
  | 'decorator'
  | 'operator'
  | 'punctuation'
  | 'text'

export interface Token {
  kind: TokenKind
  text: string
}

const KEYWORDS = new Set([
  'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else',
  'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
  'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield', 'match', 'case',
])

const CONSTANTS = new Set(['True', 'False', 'None', 'self', 'cls'])

const BUILTINS = new Set([
  'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec',
  'filter', 'float', 'format', 'getattr', 'globals', 'hasattr', 'hash', 'hex', 'id', 'input', 'int',
  'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'min', 'next', 'object',
  'oct', 'open', 'ord', 'pow', 'print', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
  'sorted', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip', '__import__', '__name__',
  'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'ZeroDivisionError', 'EOFError',
  'NameError', 'AttributeError', 'RuntimeError', 'StopIteration', 'SystemExit',
])

const NUMBER_RE = /^(?:0[xX][\da-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?[jJ]?)/
const IDENT_RE = /^[\p{L}_][\p{L}\p{N}_]*/u
const STRING_START_RE = /^(?:[rRbBuUfF]{1,2})?(?:'''|"""|'|")/
const OPERATOR_RE = /^(?:\*\*=?|\/\/=?|->|:=|<<=?|>>=?|[+\-*/%@&|^~<>!=]=?)/
const PUNCTUATION = new Set(['(', ')', '[', ']', '{', '}', ',', '.', ':', ';'])

interface OpenString {
  quote: string
}

function pushToken(line: Token[], kind: TokenKind, text: string) {
  if (!text) return
  const last = line[line.length - 1]
  if (last && last.kind === kind) last.text += text
  else line.push({ kind, text })
}

/** Index just after the closing `quote` starting the search at `from`, or -1 (honours backslash escapes). */
function findStringEnd(text: string, from: number, quote: string): number {
  let i = from
  while (i < text.length) {
    if (text[i] === '\\') {
      i += 2
      continue
    }
    if (text.startsWith(quote, i)) return i + quote.length
    i += 1
  }
  return -1
}

function lastSignificant(line: Token[]): Token | undefined {
  for (let i = line.length - 1; i >= 0; i -= 1) {
    const token = line[i]
    if (token && token.text.trim()) return token
  }
  return undefined
}

export function tokenizePython(source: string | string[]): Token[][] {
  const lines = Array.isArray(source) ? source : source.split(/\r?\n/)
  const result: Token[][] = []
  let open: OpenString | null = null

  for (const text of lines) {
    const line: Token[] = []
    let i = 0

    if (open) {
      const end = findStringEnd(text, 0, open.quote)
      if (end === -1) {
        pushToken(line, 'string', text)
        result.push(line)
        continue
      }
      pushToken(line, 'string', text.slice(0, end))
      i = end
      open = null
    }

    while (i < text.length) {
      const rest = text.slice(i)
      const ch = text[i] as string

      if (ch === ' ' || ch === '\t') {
        const ws = /^[ \t]+/.exec(rest)?.[0] ?? ch
        pushToken(line, 'text', ws)
        i += ws.length
        continue
      }
      if (ch === '#') {
        pushToken(line, 'comment', rest)
        break
      }
      const stringStart = STRING_START_RE.exec(rest)
      if (stringStart) {
        const opener = stringStart[0]
        const quote = opener.replace(/^[rRbBuUfF]+/, '')
        const end = findStringEnd(text, i + opener.length, quote)
        if (end === -1) {
          pushToken(line, 'string', rest)
          if (quote.length === 3) open = { quote }
          break
        }
        pushToken(line, 'string', text.slice(i, end))
        i = end
        continue
      }
      if (ch === '@' && !text.slice(0, i).trim()) {
        const deco = /^@[\p{L}_][\p{L}\p{N}_.]*/u.exec(rest)?.[0]
        if (deco) {
          pushToken(line, 'decorator', deco)
          i += deco.length
          continue
        }
      }
      if (/[\d.]/.test(ch)) {
        const num = NUMBER_RE.exec(rest)?.[0]
        if (num && num !== '.') {
          pushToken(line, 'number', num)
          i += num.length
          continue
        }
      }
      const ident = IDENT_RE.exec(rest)?.[0]
      if (ident) {
        const prev = lastSignificant(line)
        let kind: TokenKind = 'text'
        if (KEYWORDS.has(ident)) kind = 'keyword'
        else if (CONSTANTS.has(ident)) kind = 'constant'
        else if (prev && prev.kind === 'keyword' && (prev.text.endsWith('def') || prev.text.endsWith('class')))
          kind = 'function'
        else if (BUILTINS.has(ident) && !(prev && prev.text.endsWith('.'))) kind = 'builtin'
        // Separate adjacent identifiers ("def" + " " are distinct tokens already).
        line.push({ kind, text: ident })
        i += ident.length
        continue
      }
      const op = OPERATOR_RE.exec(rest)?.[0]
      if (op) {
        pushToken(line, 'operator', op)
        i += op.length
        continue
      }
      pushToken(line, PUNCTUATION.has(ch) ? 'punctuation' : 'text', ch)
      i += 1
    }
    result.push(line)
  }
  return result
}

/** Plain-text "tokens" for non-Python content, same shape as tokenizePython. */
export function tokenizePlain(source: string | string[]): Token[][] {
  const lines = Array.isArray(source) ? source : source.split(/\r?\n/)
  return lines.map((text) => (text ? [{ kind: 'text' as const, text }] : []))
}
