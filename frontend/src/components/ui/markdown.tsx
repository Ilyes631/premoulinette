import { useMemo, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { parseMarkdown, type MdBlock, type MdInline } from '@/lib/markdown'
import { CodeBlock } from './code-block'

function renderInline(nodes: MdInline[], keyPrefix = ''): ReactNode[] {
  return nodes.map((node, i) => {
    const key = `${keyPrefix}${i}`
    switch (node.type) {
      case 'text':
        return node.text
      case 'strong':
        return (
          <strong key={key} className="font-semibold text-fg">
            {renderInline(node.children, `${key}.`)}
          </strong>
        )
      case 'em':
        return <em key={key}>{renderInline(node.children, `${key}.`)}</em>
      case 'code':
        return (
          <code key={key} className="rounded border border-border bg-surface-2 px-1 py-px font-mono text-[0.85em] text-fg">
            {node.text}
          </code>
        )
      case 'link':
        return (
          <a
            key={key}
            href={node.href}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="text-accent-fg underline underline-offset-2 hover:no-underline"
          >
            {renderInline(node.children, `${key}.`)}
          </a>
        )
    }
  })
}

const HEADING_CLASS = ['text-base', 'text-sm', 'text-sm', 'text-sm', 'text-sm', 'text-sm']

function renderBlock(block: MdBlock, key: number): ReactNode {
  switch (block.type) {
    case 'paragraph':
      return <p key={key}>{renderInline(block.children)}</p>
    case 'heading': {
      // Explanation headings live inside panels: never emit h1/h2.
      const Tag = (`h${Math.min(6, block.level + 2)}` as 'h3' | 'h4' | 'h5' | 'h6')
      return (
        <Tag key={key} className={cn('font-semibold text-fg', HEADING_CLASS[block.level - 1])}>
          {renderInline(block.children)}
        </Tag>
      )
    }
    case 'code':
      return (
        <CodeBlock
          key={key}
          code={block.text}
          language={block.lang && /^(py|python|python3)$/i.test(block.lang) ? 'python' : 'text'}
          showLineNumbers={false}
          copyable={false}
          className="my-1"
        />
      )
    case 'list': {
      const items = block.items.map((item, i) => <li key={i}>{renderInline(item)}</li>)
      return block.ordered ? (
        <ol key={key} start={block.start} className="list-decimal space-y-1 pl-5 marker:text-fg-subtle">
          {items}
        </ol>
      ) : (
        <ul key={key} className="list-disc space-y-1 pl-5 marker:text-fg-subtle">
          {items}
        </ul>
      )
    }
    case 'quote':
      return (
        <blockquote key={key} className="border-l-2 border-border-strong pl-3 text-fg-muted">
          {renderInline(block.children)}
        </blockquote>
      )
    case 'hr':
      return <hr key={key} className="border-border" />
  }
}

export interface MarkdownProps {
  source: string
  className?: string
}

/** Safe Markdown rendering: builds React elements from a small AST, never injects HTML. */
export function Markdown({ source, className }: MarkdownProps) {
  const blocks = useMemo(() => parseMarkdown(source), [source])
  return (
    <div className={cn('space-y-3 text-sm leading-relaxed text-fg-muted', className)}>
      {blocks.map((block, i) => renderBlock(block, i))}
    </div>
  )
}
