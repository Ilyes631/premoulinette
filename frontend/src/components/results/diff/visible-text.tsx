import { cn } from '@/lib/cn'
import { splitVisible } from '@/lib/invisible'

export interface VisibleTextProps {
  text: string
  show: boolean
  /** Offset of `text` inside its line and start of the line's trailing whitespace. */
  offset?: number
  trailingFrom?: number
  className?: string
}

/**
 * Renders text with optional invisible-character glyphs. Trailing whitespace is always
 * highlighted subtly (even with glyphs hidden) because it is a classic moulinette failure.
 */
export function VisibleText({ text, show, offset, trailingFrom, className }: VisibleTextProps) {
  const parts = splitVisible(text, show, { offset, trailingFrom })
  return (
    <span className={className}>
      {parts.map((part, i) => {
        if (part.kind === 'text') return part.text
        return (
          <span
            key={i}
            data-invisible={part.kind}
            title={part.kind === 'trailing' ? 'Trailing whitespace' : undefined}
            className={cn(
              part.kind === 'trailing' && 'rounded-[2px] bg-warning/20',
              show && 'text-fg-subtle',
            )}
          >
            {part.text}
          </span>
        )
      })}
    </span>
  )
}
