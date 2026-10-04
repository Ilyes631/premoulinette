import { ArrowRight, FileCode2, Pencil, Plus, SquareFunction, SquareTerminal } from 'lucide-react'
import { TranscriptView } from '@/components/results'
import { Badge, Button, Card, EmptyState, ProvenanceBadge } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { ExerciseSpec, FunctionSpec, ScriptSpec } from '@/lib/types'
import { SectionTitle, VisibleSpaces } from './parts'
import { formatCall, formatExpected, formatRule, formatSignature } from './spec-utils'

const KIND_LABEL: Record<ExerciseSpec['kind'], string> = {
  functions: 'Functions',
  script: 'Interactive script',
  file: 'File only',
}

export interface RequirementsTabProps {
  exercises: ExerciseSpec[]
  onEdit: (index: number) => void
  onAdd: () => void
}

export function RequirementsTab({ exercises, onEdit, onAdd }: RequirementsTabProps) {
  if (!exercises.length) {
    return (
      <EmptyState
        icon={FileCode2}
        title="No exercise was found in this subject"
        description="The parser could not find a section with a file path. Add the exercises by hand, or re-parse the subject."
      >
        <Button variant="primary" onClick={onAdd}>
          <Plus aria-hidden /> Add exercise
        </Button>
      </EmptyState>
    )
  }
  const mandatory = exercises.filter((e) => !e.bonus).length
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-fg-muted">
          <span className="tabular font-medium text-fg">{mandatory}</span> mandatory ·{' '}
          <span className="tabular font-medium text-fg">{exercises.length - mandatory}</span> bonus. Review each one: the
          analysis checks exactly what is listed here.
        </p>
        <Button size="sm" onClick={onAdd}>
          <Plus aria-hidden /> Add exercise
        </Button>
      </div>
      <ol className="space-y-3">
        {exercises.map((exercise, index) => (
          <li key={`${exercise.id}-${index}`}>
            <ExerciseCard exercise={exercise} index={index} onEdit={() => onEdit(index)} />
          </li>
        ))}
      </ol>
    </div>
  )
}

export function ExerciseCard({ exercise, index, onEdit }: { exercise: ExerciseSpec; index: number; onEdit: () => void }) {
  const Icon = exercise.kind === 'script' ? SquareTerminal : SquareFunction
  return (
    <Card className="overflow-hidden" data-testid={`exercise-${exercise.id}`}>
      <header className="flex flex-wrap items-start gap-3 border-b border-border px-4 py-3.5 sm:px-5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border-strong bg-surface-2 text-fg-muted">
          <Icon className="size-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="tabular text-xs text-fg-subtle">#{index + 1}</span>
            <h3 className="text-sm font-semibold text-fg">{exercise.title || exercise.id}</h3>
            {exercise.bonus ? (
              <Badge tone="bonus">Bonus</Badge>
            ) : exercise.required ? (
              <Badge tone="pass">✓ Required</Badge>
            ) : (
              <Badge>Optional</Badge>
            )}
            <ProvenanceBadge provenance={exercise.origin.provenance} confidence={exercise.origin.confidence} />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-muted">
            <span className="inline-flex min-w-0 items-center gap-1">
              <span className="text-fg-subtle">File</span>
              <code className="truncate font-mono text-fg">{exercise.file_path}</code>
            </span>
            <span>{KIND_LABEL[exercise.kind]}</span>
            <span className="font-mono text-fg-subtle">id {exercise.id}</span>
            {exercise.constraints && <Badge tone="warning">Own constraints</Badge>}
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={onEdit} aria-label={`Edit exercise ${exercise.title || exercise.id}`}>
          <Pencil aria-hidden /> Edit
        </Button>
      </header>
      <div className="space-y-4 px-4 py-4 sm:px-5">
        {exercise.description && <p className="text-sm text-pretty text-fg-muted">{exercise.description}</p>}
        {exercise.functions.map((fn, i) => (
          <FunctionBlock key={`${fn.signature.name}-${i}`} fn={fn} />
        ))}
        {exercise.script && <ScriptBlock script={exercise.script} filePath={exercise.file_path} />}
        {!exercise.functions.length && !exercise.script && (
          <p className="text-sm text-fg-subtle">Only the presence of the file is checked.</p>
        )}
      </div>
    </Card>
  )
}

function FunctionBlock({ fn }: { fn: FunctionSpec }) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 rounded-md border border-border bg-code-bg px-2.5 py-1.5 font-mono text-[0.8125rem] break-all text-fg">
          <span className="text-syn-keyword">def</span> {formatSignature(fn.signature).slice(4)}
        </code>
        <ProvenanceBadge provenance={fn.origin.provenance} confidence={fn.origin.confidence} />
        {fn.must_return && <Badge tone="info">must return</Badge>}
        {!fn.may_print && <Badge>no print</Badge>}
      </div>
      {fn.description && <p className="text-sm text-fg-muted">{fn.description}</p>}

      {fn.rules.length > 0 && (
        <div>
          <SectionTitle>Rules</SectionTitle>
          <ul className="space-y-1.5">
            {fn.rules.map((rule, i) => {
              const text = formatRule(rule)
              return (
                <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                  <code className={cn('font-mono text-[0.8125rem]', text.otherwise ? 'text-fg-muted italic' : 'text-fg')}>
                    {text.condition}
                  </code>
                  <ArrowRight className="size-3.5 text-fg-subtle" aria-label="returns" />
                  <code className="font-mono text-[0.8125rem] text-syn-string">{text.outcome}</code>
                  <ProvenanceBadge provenance={rule.origin.provenance} confidence={rule.origin.confidence} />
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {fn.reference && (
        <div>
          <SectionTitle>Reference expression</SectionTitle>
          <code className="font-mono text-[0.8125rem] text-fg">return {fn.reference}</code>
        </div>
      )}

      {fn.tests.length > 0 && (
        <div>
          <SectionTitle>Examples</SectionTitle>
          <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
            {fn.tests.map((test) => (
              <li key={test.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 bg-surface-2/40 px-3 py-2 text-[0.8125rem]">
                <code className="min-w-0 font-mono break-all text-fg">{formatCall(test)}</code>
                <ArrowRight className="size-3.5 shrink-0 text-fg-subtle" aria-label="expected" />
                <code className="min-w-0 font-mono break-all text-syn-string">{formatExpected(test)}</code>
                <span className="ml-auto">
                  <ProvenanceBadge provenance={test.origin.provenance} confidence={test.origin.confidence} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {!fn.rules.length && !fn.tests.length && !fn.reference && (
        <p className="text-xs text-fg-subtle">
          No rule nor example: only the presence and the signature of the function can be checked.
        </p>
      )}
    </section>
  )
}

function ScriptBlock({ script, filePath }: { script: ScriptSpec; filePath: string }) {
  const command = `python3 ${filePath.split('/').pop() ?? filePath}`
  return (
    <section className="space-y-3">
      {script.prompts.length > 0 && (
        <div>
          <SectionTitle>Prompts (exact, trailing spaces shown as ␠)</SectionTitle>
          <ol className="flex flex-wrap gap-1.5">
            {script.prompts.map((prompt, i) => (
              <li key={i} className="rounded-md border border-border bg-code-bg px-2 py-1 text-[0.8125rem] text-fg">
                <VisibleSpaces text={prompt} />
              </li>
            ))}
          </ol>
        </div>
      )}
      {script.required_outputs.length > 0 && (
        <div>
          <SectionTitle>Required outputs</SectionTitle>
          <ul className="space-y-1">
            {script.required_outputs.map((out, i) => (
              <li key={i} className="text-[0.8125rem]">
                <VisibleSpaces text={out} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {script.tests.map((test, i) => (
        <div key={test.id}>
          <SectionTitle
            action={<ProvenanceBadge provenance={test.origin.provenance} confidence={test.origin.confidence} />}
          >
            {test.title || `Session ${i + 1}`} · {test.id}
          </SectionTitle>
          {test.steps && test.steps.length > 0 ? (
            <TranscriptView expected={test.steps} command={[command, ...test.argv].join(' ')} className="lg:grid-cols-1" />
          ) : (
            <pre className="overflow-x-auto rounded-lg border border-border bg-code-bg px-3 py-2 font-mono text-xs text-fg">
              {test.expected_stdout ?? 'No expected output'}
            </pre>
          )}
        </div>
      ))}
      {!script.tests.length && !script.prompts.length && (
        <p className="text-xs text-fg-subtle">No session was found for this script.</p>
      )}
    </section>
  )
}
