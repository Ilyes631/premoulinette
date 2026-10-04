import { Check, Copy } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { tokenizePlain, tokenizePython, type TokenKind } from '@/lib/highlight/python'
import { Tooltip } from './tooltip'

const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword: 'text-syn-keyword',
  constant: 'text-syn-number',
  builtin: 'text-syn-builtin',
  string: 'text-syn-string',
  number: 'text-syn-number',
  comment: 'text-syn-comment italic',
  function: 'text-syn-function',
  decorator: 'text-syn-decorator',
  operator: 'text-fg-muted',
  punctuation: 'text-fg-muted',
  text: '',
}

export type CodeLanguage = 'python' | 'text'

export function languageFromPath(path: string | null | undefined): CodeLanguage {
  return path && /\.pyw?$/i.test(path) ? 'python' : 'text'
}

export interface CodeBlockProps {
  /** Source as one string, or already split lines. */
  code: string | string[]
  language?: CodeLanguage
  /** Number of the first line (CodeExcerpt.start_line). */
  startLine?: number
  /** Absolute line numbers to highlight. */
  highlight?: number[]
  showLineNumbers?: boolean
  /** Header label, usually the file path. */
  title?: ReactNode
  /** Extra header controls (e.g. "Open file"). */
  actions?: ReactNode
  /** Scroll this absolute line into view on mount. */
  focusLine?: number
  maxHeight?: number | string
  copyable?: boolean
  className?: string
}

export function CodeBlock({
  code,
  language = 'python',
  startLine = 1,
  highlight = [],
  showLineNumbers = true,
  title,
  actions,
  focusLine,
  maxHeight,
  copyable = true,
  className,
}: CodeBlockProps) {
  const lines = useMemo(() => {
    const list = Array.isArray(code) ? code : code.replace(/\r\n?/g, '\n').split('\n')
    // Drop the empty line produced by a final newline.
    return !Array.isArray(code) && list.length > 1 && list[list.length - 1] === '' ? list.slice(0, -1) : list
  }, [code])
  const tokens = useMemo(() => (language === 'python' ? tokenizePython(lines) : tokenizePlain(lines)), [lines, language])
  const highlighted = useMemo(() => new Set(highlight), [highlight])
  const focusRef = useRef<HTMLSpanElement>(null)
  const gutterWidth = String(startLine + lines.length - 1).length

  useEffect(() => {
    focusRef.current?.scrollIntoView({ block: 'center' })
  }, [focusLine])

  const text = lines.join('\n')
  const header = title || actions || copyable

  return (
    <div className={cn('overflow-hidden rounded-lg border border-border bg-code-bg', className)}>
      {header && (
        <div className="flex min-h-9 items-center gap-2 border-b border-border bg-surface-2/50 py-1 pr-1.5 pl-3">
          <div className="min-w-0 flex-1 truncate font-mono text-xs text-fg-muted">{title}</div>
          {actions}
          {copyable && <CopyButton text={text} />}
        </div>
      )}
      <div className="overflow-auto" style={{ maxHeight }}>
        <pre className="min-w-full py-2 font-mono text-[0.8125rem] leading-6">
          <code className="block w-max min-w-full">
            {tokens.map((lineTokens, index) => {
              const lineNo = startLine + index
              const isHl = highlighted.has(lineNo)
              return (
                <span
                  key={lineNo}
                  ref={lineNo === focusLine ? focusRef : undefined}
                  data-line={lineNo}
                  data-highlighted={isHl || undefined}
                  className={cn(
                    'flex pr-4',
                    isHl && 'bg-warning/10 shadow-[inset_2px_0_0_var(--pm-warning)]',
                  )}
                >
                  {showLineNumbers && (
                    <span
                      aria-hidden
                      className={cn(
                        'sticky left-0 shrink-0 bg-code-bg pr-3 pl-3 text-right text-fg-subtle/70 select-none tabular',
                        isHl && 'text-warning',
                      )}
                      style={{ width: `${gutterWidth + 3}ch` }}
                    >
                      {lineNo}
                    </span>
                  )}
                  <span className={cn('whitespace-pre', !showLineNumbers && 'pl-3')}>
                    {lineTokens.length === 0
                      ? ' '
                      : lineTokens.map((t, i) => (
                          <span key={i} className={TOKEN_CLASS[t.kind] || undefined}>
                            {t.text}
                          </span>
                        ))}
                  </span>
                </span>
              )
            })}
          </code>
        </pre>
      </div>
    </div>
  )
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 1500)
    return () => clearTimeout(timer)
  }, [copied])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      // clipboard denied: nothing else to do
    }
  }

  return (
    <Tooltip content={copied ? 'Copied' : label}>
      <button
        type="button"
        onClick={copy}
        aria-label={label}
        className="inline-flex size-7 items-center justify-center rounded-md text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
      >
        {copied ? <Check className="size-3.5 text-pass" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      </button>
    </Tooltip>
  )
}
