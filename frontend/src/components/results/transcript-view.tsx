import { SquareTerminal } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { formatLocation } from '@/lib/format'
import type { Location, TranscriptEvent } from '@/lib/types'

export interface TranscriptStep {
  kind: string
  text: string
}

export interface TranscriptViewProps {
  /** Expected session from the subject (Evidence.expected_steps / ScriptTest.steps). */
  expected?: TranscriptStep[] | null
  /** What the student program actually did (Evidence.transcript). */
  actual?: TranscriptEvent[] | null
  /** Command shown on the first line, e.g. "python3 launch_sequence.py". */
  command?: string | null
  className?: string
}

function InputText({ text }: { text: string }) {
  return (
    <span data-kind="input">
      <span className="rounded-[3px] bg-terminal-input/15 text-terminal-input">{text}</span>
      <span className="text-terminal-muted" aria-label="Enter">
        ↵
      </span>
      {'\n'}
    </span>
  )
}

function renderChunk(kind: string, text: string, key: number, location?: Location | null): ReactNode {
  if (kind === 'input') return <InputText key={key} text={text} />
  return (
    <span
      key={key}
      data-kind={kind}
      className={kind === 'stderr' ? 'text-terminal-stderr' : undefined}
      title={location ? `Printed at ${formatLocation(location)}` : undefined}
    >
      {text}
    </span>
  )
}

function Pane({ title, subtitle, command, children }: { title: string; subtitle?: string; command?: string | null; children: ReactNode }) {
  return (
    <figure className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-terminal-border bg-terminal-bg">
      <figcaption className="flex items-center gap-2 border-b border-terminal-border px-3 py-2">
        <SquareTerminal className="size-3.5 text-terminal-muted" aria-hidden />
        <span className="text-xs font-semibold text-terminal-fg">{title}</span>
        {subtitle && <span className="truncate text-2xs text-terminal-muted">{subtitle}</span>}
      </figcaption>
      <pre className="min-h-24 overflow-x-auto px-3 py-2.5 font-mono text-[0.8125rem] leading-6 whitespace-pre text-terminal-fg">
        {command && <span className="text-terminal-muted">{`$ ${command}\n`}</span>}
        {children}
      </pre>
    </figure>
  )
}

/** Terminal-like rendering of the expected session next to what the program did. Typed input is highlighted. */
export function TranscriptView({ expected, actual, command, className }: TranscriptViewProps) {
  if (!expected?.length && !actual?.length) return null
  return (
    <div className={cn('grid gap-3 lg:grid-cols-2', className)}>
      {expected && expected.length > 0 && (
        <Pane title="Expected session" subtitle="from the subject" command={command}>
          {expected.map((step, i) => renderChunk(step.kind, step.text, i))}
        </Pane>
      )}
      {actual && (
        <Pane title="Your program" subtitle={actual.length ? 'captured in the sandbox' : 'no output'} command={command}>
          {actual.map((event, i) => renderChunk(event.kind, event.text, i, event.location))}
        </Pane>
      )}
    </div>
  )
}
