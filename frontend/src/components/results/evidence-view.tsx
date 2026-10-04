import { Bug, Clock, FileCode } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { CodeBlock, languageFromPath } from '@/components/ui/code-block'
import { basename, formatDuration } from '@/lib/format'
import { toVisible } from '@/lib/invisible'
import type { CheckResult, Evidence, ExceptionInfo, Location } from '@/lib/types'
import { DiffView } from './diff/diff-view'
import { SourceChip } from './diff/diff-rows'
import { TranscriptView } from './transcript-view'
import { ValueCompare } from './value-compare'

interface Props {
  check: CheckResult
  evidence: Evidence
  onOpenSource?: (location: Location) => void
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold tracking-wider text-fg-subtle uppercase">{title}</h3>
      {children}
    </section>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3 text-sm">
      <dt className="text-fg-subtle">{label}</dt>
      <dd className="min-w-0 break-words text-fg">{children}</dd>
    </div>
  )
}

function ExceptionView({ exception, onOpenSource }: { exception: ExceptionInfo; onOpenSource?: (l: Location) => void }) {
  return (
    <div className="space-y-2 rounded-lg border border-fail/25 bg-fail/5 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Bug className="size-4 text-fail" aria-hidden />
        <code className="font-mono text-sm font-semibold text-fail">{exception.type}</code>
        <span className="min-w-0 font-mono text-sm break-words text-fg">{exception.message}</span>
        {exception.location && <SourceChip location={exception.location} onOpenSource={onOpenSource} />}
      </div>
      {exception.traceback && <CodeBlock code={exception.traceback} language="text" showLineNumbers={false} title="Traceback" />}
    </div>
  )
}

function scriptCommand(check: CheckResult, evidence: Evidence): string | null {
  const file = check.file ?? check.location?.file
  if (!file) return null
  return ['python3', basename(file), ...(evidence.argv ?? [])].join(' ')
}

/** Everything the deterministic check recorded: call, values, diffs, transcript, exception, code. */
export function EvidenceView({ check, evidence, onOpenSource }: Props) {
  const hasCallInfo = evidence.call || evidence.rule || evidence.stdin || evidence.exit_code !== null
  const showValues = evidence.expected_value || evidence.actual_value
  const missingActual = evidence.exception
    ? `No value: the call raised ${evidence.exception.type}`
    : evidence.timed_out
      ? 'No value: the call timed out'
      : undefined
  const detailEntries = Object.entries(evidence.details ?? {})
  const code = evidence.code

  return (
    <div className="space-y-5">
      {hasCallInfo && (
        <Section title="Test">
          <dl className="space-y-1.5">
            {evidence.call && (
              <Field label="Call">
                <code className="font-mono">{evidence.call}</code>
              </Field>
            )}
            {evidence.rule && <Field label="Rule">{evidence.rule}</Field>}
            {evidence.stdin && (
              <Field label="Input">
                <code className="font-mono break-all">{toVisible(evidence.stdin)}</code>
              </Field>
            )}
            {evidence.exit_code !== null && <Field label="Exit code">{evidence.exit_code}</Field>}
          </dl>
        </Section>
      )}

      {showValues && (
        <Section title="Return value">
          <ValueCompare
            expected={evidence.expected_value}
            actual={evidence.actual_value}
            valueDiff={evidence.value_diff}
            missingActualText={missingActual}
            onOpenSource={onOpenSource}
          />
        </Section>
      )}
      {!showValues && evidence.value_diff && !evidence.value_diff.equal && (
        <Section title="Difference">
          <DiffView diff={evidence.value_diff} onOpenSource={onOpenSource} />
        </Section>
      )}

      {evidence.stdout_diff && (
        <Section title="Standard output">
          <DiffView diff={evidence.stdout_diff} onOpenSource={onOpenSource} />
        </Section>
      )}
      {!evidence.stdout_diff && evidence.actual_stdout && (
        <Section title="Printed output">
          <CodeBlock code={evidence.actual_stdout} language="text" showLineNumbers={false} />
        </Section>
      )}

      {(evidence.transcript || evidence.expected_steps) && (
        <Section title="Terminal session">
          <TranscriptView
            expected={evidence.expected_steps?.map((s) => ({ kind: s.kind ?? 'output', text: s.text ?? '' }))}
            actual={evidence.transcript}
            command={scriptCommand(check, evidence)}
          />
        </Section>
      )}

      {evidence.exception && (
        <Section title="Exception">
          <ExceptionView exception={evidence.exception} onOpenSource={onOpenSource} />
        </Section>
      )}
      {evidence.timed_out && (
        <p className="flex items-center gap-2 text-sm text-fail">
          <Clock className="size-4" aria-hidden /> The program did not finish in time (infinite loop or waiting for input?).
        </p>
      )}
      {evidence.stderr && !evidence.exception && (
        <Section title="Standard error">
          <CodeBlock code={evidence.stderr} language="text" showLineNumbers={false} />
        </Section>
      )}

      {code && (
        <Section title="Code">
          <CodeBlock
            code={code.lines}
            startLine={code.start_line}
            highlight={code.highlight}
            language={languageFromPath(code.file)}
            title={code.file}
            actions={
              onOpenSource && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    onOpenSource({ file: code.file, line: code.highlight[0] ?? code.start_line, end_line: null, col: null })
                  }
                >
                  <FileCode aria-hidden /> Open file
                </Button>
              )
            }
          />
        </Section>
      )}

      {detailEntries.length > 0 && (
        <Section title="Details">
          <dl className="space-y-1.5">
            {detailEntries.map(([key, value]) => (
              <Field key={key} label={key.replace(/_/g, ' ')}>
                <code className="font-mono text-xs break-words whitespace-pre-wrap">
                  {typeof value === 'string' ? value : JSON.stringify(value)}
                </code>
              </Field>
            ))}
          </dl>
        </Section>
      )}

      {evidence.duration_ms !== null && (
        <p className="text-2xs text-fg-subtle">Ran in {formatDuration(evidence.duration_ms)} in the sandbox.</p>
      )}
    </div>
  )
}
