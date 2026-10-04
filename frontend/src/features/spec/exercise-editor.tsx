/**
 * Structured editor for one exercise (Sheet). Edits a deep copy; "Save" validates minimally on
 * the client, marks edited items with provenance "user" and hands the exercise to `onSave`,
 * which PUTs the whole spec (server 422 errors come back through `serverErrors`).
 */
import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react'
import { useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import {
  Badge,
  Button,
  Input,
  ProvenanceBadge,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Switch,
  Tooltip,
} from '@/components/ui'
import { cn } from '@/lib/cn'
import type { ExerciseSpec, FunctionSpec, InteractionStep, ScriptSpec } from '@/lib/types'
import { ConstructPicker } from './construct-picker'
import { ChipInput, FieldLabel, InlineWarning, IssueList, SectionTitle, TextArea, VisibleSpaces } from './parts'
import {
  normalizeName,
  cloneSpec,
  emptyConstraints,
  markEdited,
  newFunction,
  newFunctionTest,
  newParam,
  newRule,
  newScript,
  newScriptTest,
  normalizeExercise,
  validateExerciseDraft,
  type DraftIssue,
} from './spec-utils'

export interface ExerciseEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Exercise as stored (null when adding a new one: `initial` is then the fresh draft). */
  original: ExerciseSpec | null
  initial: ExerciseSpec
  otherExerciseIds: Set<string>
  otherTestIds: Set<string>
  onSave: (exercise: ExerciseSpec) => Promise<boolean>
  onDelete?: () => Promise<boolean>
  saving: boolean
  serverErrors: DraftIssue[]
}

type Mutator = (draft: ExerciseSpec) => void

export function ExerciseEditor(props: ExerciseEditorProps) {
  const { open, onOpenChange, original, initial } = props
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent widthClassName="sm:max-w-3xl">
        {open && <EditorBody key={`${initial.id}-${original ? 'edit' : 'new'}`} {...props} />}
      </SheetContent>
    </Sheet>
  )
}

function EditorBody({
  onOpenChange,
  original,
  initial,
  otherExerciseIds,
  otherTestIds,
  onSave,
  onDelete,
  saving,
  serverErrors,
}: ExerciseEditorProps) {
  const [draft, setDraft] = useState<ExerciseSpec>(() => cloneSpec(initial))
  const [clientIssues, setClientIssues] = useState<DraftIssue[]>([])
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!confirmDelete) return
    const timer = setTimeout(() => setConfirmDelete(false), 4000)
    return () => clearTimeout(timer)
  }, [confirmDelete])

  const update = (mutate: Mutator) =>
    setDraft((current) => {
      const next = cloneSpec(current)
      mutate(next)
      return next
    })

  const allTestIds = useMemo(() => {
    const ids = new Set(otherTestIds)
    for (const fn of draft.functions) for (const t of fn.tests) ids.add(t.id)
    for (const t of draft.script?.tests ?? []) ids.add(t.id)
    return ids
  }, [draft, otherTestIds])

  const submit = async () => {
    const normalized = normalizeExercise(draft)
    const issues = validateExerciseDraft(normalized, otherExerciseIds, otherTestIds)
    setClientIssues(issues)
    if (issues.length) return
    const ok = await onSave(markEdited(original, normalized))
    if (ok) onOpenChange(false)
  }

  const remove = async () => {
    if (!onDelete) return
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    const ok = await onDelete()
    if (ok) onOpenChange(false)
  }

  const hasFunctions = draft.kind === 'functions' || draft.functions.length > 0
  const hasScript = draft.kind === 'script' || draft.script !== null

  return (
    <>
      <SheetHeader>
        <div className="flex flex-wrap items-center gap-2">
          <SheetTitle className="text-base font-semibold text-fg">
            {original ? `Edit “${original.title || original.id}”` : 'New exercise'}
          </SheetTitle>
          <ProvenanceBadge provenance={draft.origin.provenance} confidence={draft.origin.confidence} />
        </div>
        <SheetDescription className="mt-1 text-xs text-fg-muted">
          Values are Python literals: strings need quotes (<code className="font-mono">'Hard landing'</code>), booleans
          are <code className="font-mono">True</code>/<code className="font-mono">False</code>. Edited items are marked
          “User”.
        </SheetDescription>
      </SheetHeader>

      <SheetBody className="space-y-6 px-5 py-5">
        <GeneralSection draft={draft} update={update} />

        {hasFunctions && (
          <section aria-label="Functions" className="space-y-4">
            <SectionTitle
              action={
                <Button size="sm" variant="ghost" onClick={() => update((d) => void d.functions.push(newFunction()))}>
                  <Plus aria-hidden /> Add function
                </Button>
              }
            >
              Functions
            </SectionTitle>
            {draft.functions.length === 0 && <p className="text-sm text-fg-subtle">No function yet.</p>}
            {draft.functions.map((fn, fi) => (
              <FunctionEditor key={fi} fn={fn} index={fi} update={update} takenTestIds={allTestIds} />
            ))}
          </section>
        )}

        {hasScript && <ScriptEditor draft={draft} update={update} takenTestIds={allTestIds} />}

        <ConstraintsOverride draft={draft} update={update} />
      </SheetBody>

      <div className="space-y-3 border-t border-border px-5 py-3">
        <IssueList issues={clientIssues} title="Fix these fields before saving" />
        <IssueList issues={serverErrors} title="The server rejected the contract" />
        <div className="flex flex-wrap items-center gap-2">
          {onDelete && (
            <Button variant="danger" size="sm" onClick={remove} disabled={saving}>
              <Trash2 aria-hidden /> {confirmDelete ? 'Click again to delete' : 'Delete exercise'}
            </Button>
          )}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={submit} loading={saving}>
              Save exercise
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}

// ---- general -----------------------------------------------------------------------------------

function TextField({
  label,
  value,
  onChange,
  placeholder,
  mono,
  hint,
  className,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  mono?: boolean
  hint?: ReactNode
  className?: string
}) {
  const id = useId()
  return (
    <div className={cn('min-w-0', className)}>
      <FieldLabel htmlFor={id} hint={hint}>
        {label}
      </FieldLabel>
      <Input
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={cn(mono && 'font-mono text-[0.8125rem]')}
        spellCheck={mono ? false : undefined}
      />
    </div>
  )
}

function GeneralSection({ draft, update }: { draft: ExerciseSpec; update: (m: Mutator) => void }) {
  const kindId = useId()
  return (
    <section aria-label="Exercise" className="space-y-3">
      <SectionTitle>Exercise</SectionTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Title" value={draft.title} onChange={(v) => update((d) => void (d.title = v))} />
        <TextField label="Id" mono value={draft.id} onChange={(v) => update((d) => void (d.id = v.trim()))} hint="unique" />
        <TextField
          label="File path"
          mono
          className="sm:col-span-2"
          value={draft.file_path}
          placeholder="MysteryInc/FirstLaunch/kelvin.py"
          hint="exact case, from the repository root"
          onChange={(v) => update((d) => void (d.file_path = v))}
        />
        <div>
          <FieldLabel htmlFor={kindId}>Kind</FieldLabel>
          <select
            id={kindId}
            value={draft.kind}
            onChange={(e) =>
              update((d) => {
                d.kind = e.target.value as ExerciseSpec['kind']
                if (d.kind === 'script' && !d.script) d.script = newScript()
                if (d.kind === 'functions' && !d.functions.length) d.functions.push(newFunction())
              })
            }
            className="h-9 w-full rounded-lg border border-border-strong bg-bg-subtle px-2.5 text-sm text-fg focus-visible:border-accent"
          >
            <option value="functions">Functions (imported and called)</option>
            <option value="script">Script (run with stdin)</option>
            <option value="file">File only</option>
          </select>
        </div>
        <div className="flex flex-col justify-end gap-2 pb-1">
          <Switch
            label="Required"
            checked={draft.required && !draft.bonus}
            disabled={draft.bonus}
            onCheckedChange={(v) => update((d) => void (d.required = v))}
          />
          <Switch
            label="Bonus (never blocks the verdict)"
            checked={draft.bonus}
            onCheckedChange={(v) =>
              update((d) => {
                d.bonus = v
                if (v) d.required = false
              })
            }
          />
        </div>
      </div>
      {draft.kind === 'functions' && (
        <Switch
          label="Code may run when the file is imported (top-level prints/inputs allowed)"
          checked={draft.import_side_effects_allowed}
          onCheckedChange={(v) => update((d) => void (d.import_side_effects_allowed = v))}
        />
      )}
    </section>
  )
}

// ---- functions ---------------------------------------------------------------------------------

function IconButton({ label, onClick, children, disabled }: { label: string; onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return (
    <Tooltip content={label}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg disabled:opacity-40 [&_svg]:size-3.5"
      >
        {children}
      </button>
    </Tooltip>
  )
}

function SmallInput({ label, value, onChange, placeholder, className }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; className?: string }) {
  return (
    <Input
      aria-label={label}
      value={value}
      placeholder={placeholder}
      spellCheck={false}
      onChange={(e) => onChange(e.target.value)}
      className={cn('h-8 font-mono text-[0.8125rem]', className)}
    />
  )
}

function FunctionEditor({
  fn,
  index,
  update,
  takenTestIds,
}: {
  fn: FunctionSpec
  index: number
  update: (m: Mutator) => void
  takenTestIds: Set<string>
}) {
  const at = (mutate: (f: FunctionSpec) => void) =>
    update((d) => {
      const target = d.functions[index]
      if (target) mutate(target)
    })
  const name = fn.signature.name || `function ${index + 1}`

  return (
    <div className="space-y-4 rounded-xl border border-border bg-surface-2/40 p-4" data-testid={`function-editor-${index}`}>
      <div className="flex items-start gap-2">
        <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-[1fr_10rem]">
          <TextField
            label="Function name"
            mono
            value={fn.signature.name}
            onChange={(v) =>
              at((f) => {
                const old = f.signature.name
                f.signature.name = v.trim()
                for (const t of f.tests) if (t.function === old) t.function = f.signature.name
              })
            }
          />
          <TextField
            label="Returns"
            mono
            value={fn.signature.return_annotation ?? ''}
            placeholder="bool"
            onChange={(v) => at((f) => void (f.signature.return_annotation = v))}
          />
        </div>
        <IconButton label={`Remove function ${name}`} onClick={() => update((d) => void d.functions.splice(index, 1))}>
          <Trash2 aria-hidden />
        </IconButton>
      </div>

      <div>
        <SectionTitle
          action={
            <Button size="sm" variant="ghost" onClick={() => at((f) => void f.signature.params.push(newParam()))}>
              <Plus aria-hidden /> Parameter
            </Button>
          }
        >
          Parameters
        </SectionTitle>
        {fn.signature.params.length === 0 && <p className="text-xs text-fg-subtle">No parameter.</p>}
        <ul className="space-y-1.5">
          {fn.signature.params.map((p, pi) => (
            <li key={pi} className="flex items-center gap-1.5">
              <SmallInput label={`Parameter ${pi + 1} name`} placeholder="name" value={p.name} onChange={(v) => at((f) => {
                const target = f.signature.params[pi]
                if (target) target.name = v
              })} />
              <SmallInput label={`Parameter ${pi + 1} annotation`} placeholder="int" value={p.annotation ?? ''} onChange={(v) => at((f) => {
                const target = f.signature.params[pi]
                if (target) target.annotation = v
              })} />
              <SmallInput label={`Parameter ${pi + 1} default`} placeholder="default" value={p.default ?? ''} onChange={(v) => at((f) => {
                const target = f.signature.params[pi]
                if (target) target.default = v
              })} />
              <IconButton label={`Remove parameter ${p.name || pi + 1}`} onClick={() => at((f) => void f.signature.params.splice(pi, 1))}>
                <X aria-hidden />
              </IconButton>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2">
        <Switch label="Must return a value" checked={fn.must_return} onCheckedChange={(v) => at((f) => void (f.must_return = v))} />
        <Switch label="May print" checked={fn.may_print} onCheckedChange={(v) => at((f) => void (f.may_print = v))} />
      </div>

      <div>
        <SectionTitle
          action={
            <Button size="sm" variant="ghost" onClick={() => at((f) => void f.rules.push(newRule()))} aria-label={`Add rule to ${name}`}>
              <Plus aria-hidden /> Rule
            </Button>
          }
        >
          Rules (when → returns)
        </SectionTitle>
        {fn.rules.length === 0 && <p className="text-xs text-fg-subtle">No rule. Rules let PréMoulinette derive boundary tests.</p>}
        <ul className="space-y-1.5">
          {fn.rules.map((rule, ri) => (
            <li key={ri} className="flex items-center gap-1.5" data-testid="rule-row">
              <SmallInput
                label={`Rule ${ri + 1} condition`}
                placeholder="otherwise (empty)"
                value={rule.when ?? ''}
                onChange={(v) => at((f) => {
                  const target = f.rules[ri]
                  if (target) target.when = v
                })}
              />
              <span className="shrink-0 text-fg-subtle" aria-hidden>
                →
              </span>
              <SmallInput
                label={`Rule ${ri + 1} returns`}
                placeholder="True"
                className="sm:max-w-48"
                value={rule.returns ?? ''}
                onChange={(v) => at((f) => {
                  const target = f.rules[ri]
                  if (target) target.returns = v
                })}
              />
              <IconButton label={`Remove rule ${ri + 1}`} onClick={() => at((f) => void f.rules.splice(ri, 1))}>
                <X aria-hidden />
              </IconButton>
            </li>
          ))}
        </ul>
      </div>

      <TextField
        label="Reference expression"
        mono
        hint="optional — e.g. celsius + 273.15"
        value={fn.reference ?? ''}
        onChange={(v) => at((f) => void (f.reference = v))}
      />

      <div>
        <SectionTitle
          action={
            <Button size="sm" variant="ghost" onClick={() => at((f) => void f.tests.push(newFunctionTest(f, takenTestIds)))}>
              <Plus aria-hidden /> Test
            </Button>
          }
        >
          Tests (call → expected)
        </SectionTitle>
        {fn.tests.length === 0 && <p className="text-xs text-fg-subtle">No explicit example.</p>}
        <ul className="space-y-2">
          {fn.tests.map((test, ti) => (
            <li key={test.id} className="rounded-lg border border-border bg-surface px-3 py-2.5">
              <div className="mb-2 flex items-center gap-2">
                <code className="truncate font-mono text-2xs text-fg-subtle">{test.id}</code>
                <ProvenanceBadge provenance={test.origin.provenance} confidence={test.origin.confidence} />
                <span className="ml-auto" />
                <IconButton label={`Remove test ${test.id}`} onClick={() => at((f) => void f.tests.splice(ti, 1))}>
                  <Trash2 aria-hidden />
                </IconButton>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 font-mono text-[0.8125rem]">
                <span className="text-fg-muted">{fn.signature.name || '?'}(</span>
                {test.args.map((arg, ai) => (
                  <span key={ai} className="flex items-center gap-1">
                    <SmallInput
                      label={`Test ${ti + 1} argument ${ai + 1}`}
                      placeholder={fn.signature.params[ai]?.name ?? `arg${ai + 1}`}
                      value={arg}
                      className="w-28"
                      onChange={(v) => at((f) => {
                        const t = f.tests[ti]
                        if (t) t.args[ai] = v
                      })}
                    />
                    <IconButton label={`Remove argument ${ai + 1}`} onClick={() => at((f) => void f.tests[ti]?.args.splice(ai, 1))}>
                      <X aria-hidden />
                    </IconButton>
                  </span>
                ))}
                <IconButton label="Add argument" onClick={() => at((f) => void f.tests[ti]?.args.push(''))}>
                  <Plus aria-hidden />
                </IconButton>
                <span className="text-fg-muted">) →</span>
                <SmallInput
                  label={`Test ${ti + 1} expected value`}
                  placeholder="True"
                  className="w-36"
                  value={test.expected_return ?? ''}
                  onChange={(v) => at((f) => {
                    const t = f.tests[ti]
                    if (t) t.expected_return = v
                  })}
                />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

// ---- scripts -----------------------------------------------------------------------------------

function ScriptEditor({ draft, update, takenTestIds }: { draft: ExerciseSpec; update: (m: Mutator) => void; takenTestIds: Set<string> }) {
  const script = draft.script
  const at = (mutate: (s: ScriptSpec) => void) =>
    update((d) => {
      if (!d.script) d.script = newScript()
      mutate(d.script)
    })
  if (!script) {
    return (
      <section aria-label="Script" className="space-y-2">
        <SectionTitle>Script</SectionTitle>
        <Button size="sm" onClick={() => at(() => undefined)}>
          <Plus aria-hidden /> Add script behaviour
        </Button>
      </section>
    )
  }
  return (
    <section aria-label="Script" className="space-y-4">
      <SectionTitle
        action={
          <Button size="sm" variant="ghost" onClick={() => update((d) => void (d.script = null))}>
            <Trash2 aria-hidden /> Remove script part
          </Button>
        }
      >
        Script
      </SectionTitle>

      <div>
        <SectionTitle
          action={
            <Button size="sm" variant="ghost" onClick={() => at((s) => void s.prompts.push(''))}>
              <Plus aria-hidden /> Prompt
            </Button>
          }
        >
          input() prompts, in order
        </SectionTitle>
        {script.prompts.length === 0 && <p className="text-xs text-fg-subtle">No prompt.</p>}
        <ul className="space-y-1.5">
          {script.prompts.map((prompt, pi) => (
            <li key={pi} className="flex items-center gap-2">
              <SmallInput
                label={`Prompt ${pi + 1}`}
                value={prompt}
                placeholder="Pilot name: "
                onChange={(v) => at((s) => void (s.prompts[pi] = v))}
              />
              <span className="hidden min-w-32 shrink-0 rounded-md border border-border bg-code-bg px-2 py-1 text-xs sm:inline" aria-hidden>
                <VisibleSpaces text={prompt || ' '} />
              </span>
              <IconButton label={`Remove prompt ${pi + 1}`} onClick={() => at((s) => void s.prompts.splice(pi, 1))}>
                <X aria-hidden />
              </IconButton>
            </li>
          ))}
        </ul>
        {script.prompts.some((p) => p !== '' && !p.endsWith(' ') && /[:?]$/.test(p)) && (
          <InlineWarning className="mt-2">
            A prompt ending with “:” or “?” usually keeps a trailing space. Check the subject: the moulinette compares
            prompts byte for byte.
          </InlineWarning>
        )}
      </div>

      <div className="space-y-3">
        <SectionTitle
          action={
            <Button size="sm" variant="ghost" onClick={() => at((s) => void s.tests.push(newScriptTest(draft.id, takenTestIds)))}>
              <Plus aria-hidden /> Session
            </Button>
          }
        >
          Sessions (expected terminal transcript)
        </SectionTitle>
        {script.tests.length === 0 && <p className="text-xs text-fg-subtle">No session.</p>}
        {script.tests.map((test, ti) => (
          <SessionEditor
            key={test.id}
            title={test.title ?? ''}
            id={test.id}
            steps={test.steps ?? []}
            provenance={<ProvenanceBadge provenance={test.origin.provenance} confidence={test.origin.confidence} />}
            onTitle={(v) => at((s) => {
              const t = s.tests[ti]
              if (t) t.title = v || null
            })}
            onSteps={(steps) => at((s) => {
              const t = s.tests[ti]
              if (t) t.steps = steps
            })}
            onRemove={() => at((s) => void s.tests.splice(ti, 1))}
          />
        ))}
      </div>
    </section>
  )
}

function SessionEditor({
  id,
  title,
  steps,
  provenance,
  onTitle,
  onSteps,
  onRemove,
}: {
  id: string
  title: string
  steps: InteractionStep[]
  provenance: ReactNode
  onTitle: (v: string) => void
  onSteps: (steps: InteractionStep[]) => void
  onRemove: () => void
}) {
  const set = (i: number, patch: Partial<InteractionStep>) =>
    onSteps(steps.map((s, j) => (j === i ? { ...s, ...patch } : s)))
  const move = (i: number, delta: number) => {
    const j = i + delta
    if (j < 0 || j >= steps.length) return
    const next = [...steps]
    const a = next[i]
    const b = next[j]
    if (!a || !b) return
    next[i] = b
    next[j] = a
    onSteps(next)
  }
  return (
    <div className="space-y-2.5 rounded-xl border border-border bg-surface-2/40 p-3.5">
      <div className="flex items-center gap-2">
        <code className="truncate font-mono text-2xs text-fg-subtle">{id}</code>
        {provenance}
        <span className="ml-auto" />
        <IconButton label={`Remove session ${id}`} onClick={onRemove}>
          <Trash2 aria-hidden />
        </IconButton>
      </div>
      <SmallInput label="Session title" placeholder="Session title (optional)" value={title} onChange={onTitle} className="font-sans" />
      <ol className="space-y-1.5">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-1.5">
            <select
              aria-label={`Step ${i + 1} kind`}
              value={step.kind}
              onChange={(e) => set(i, { kind: e.target.value as InteractionStep['kind'] })}
              className={cn(
                'h-8 w-24 shrink-0 rounded-md border border-border-strong bg-bg-subtle px-1.5 text-xs',
                step.kind === 'input' ? 'text-warning' : 'text-fg',
              )}
            >
              <option value="output">Output</option>
              <option value="input">Input</option>
            </select>
            {step.kind === 'input' ? (
              <SmallInput label={`Step ${i + 1} typed input`} placeholder="typed line (no newline)" value={step.text} onChange={(v) => set(i, { text: v })} />
            ) : (
              <div className="min-w-0 flex-1">
                <TextArea
                  aria-label={`Step ${i + 1} expected output`}
                  rows={Math.min(6, Math.max(1, step.text.split('\n').length))}
                  value={step.text}
                  spellCheck={false}
                  onChange={(e) => set(i, { text: e.target.value })}
                  className="py-1.5"
                />
                {step.text.split('\n').some((line) => line.endsWith(' ')) && (
                  <p className="mt-0.5 text-2xs text-fg-subtle">
                    Trailing spaces kept: <VisibleSpaces text={step.text.split('\n').find((l) => l.endsWith(' ')) ?? ''} />
                  </p>
                )}
              </div>
            )}
            <IconButton label={`Move step ${i + 1} up`} onClick={() => move(i, -1)} disabled={i === 0}>
              <ArrowUp aria-hidden />
            </IconButton>
            <IconButton label={`Move step ${i + 1} down`} onClick={() => move(i, 1)} disabled={i === steps.length - 1}>
              <ArrowDown aria-hidden />
            </IconButton>
            <IconButton label={`Remove step ${i + 1}`} onClick={() => onSteps(steps.filter((_, j) => j !== i))}>
              <X aria-hidden />
            </IconButton>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="ghost" onClick={() => onSteps([...steps, { kind: 'output', text: '' }])}>
          <Plus aria-hidden /> Output
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onSteps([...steps, { kind: 'input', text: '' }])}>
          <Plus aria-hidden /> Input
        </Button>
        <span className="self-center text-2xs text-fg-subtle">Output text is compared exactly; inputs are fed to stdin.</span>
      </div>
    </div>
  )
}

// ---- constraints -------------------------------------------------------------------------------

function ConstraintsOverride({ draft, update }: { draft: ExerciseSpec; update: (m: Mutator) => void }) {
  const c = draft.constraints
  const at = (mutate: (x: NonNullable<ExerciseSpec['constraints']>) => void) =>
    update((d) => {
      if (d.constraints) mutate(d.constraints)
    })
  return (
    <section aria-label="Constraints override" className="space-y-3">
      <SectionTitle>Constraints for this exercise</SectionTitle>
      <Switch
        label="Override the global constraints"
        checked={c !== null}
        onCheckedChange={(v) => update((d) => void (d.constraints = v ? emptyConstraints() : null))}
      />
      {c && (
        <div className="grid gap-3 sm:grid-cols-2">
          <ChipInput label="Forbidden builtins" tone="fail" values={c.forbidden_builtins} normalize={normalizeName} placeholder="abs, max…" onChange={(v) => at((x) => void (x.forbidden_builtins = v))} />
          <div className="space-y-1.5">
            <ChipInput
              label="Allowed builtins (allow-list)"
              tone="pass"
              values={c.allowed_builtins ?? []}
              normalize={normalizeName}
              disabled={c.allowed_builtins === null}
              placeholder={c.allowed_builtins === null ? 'No allow-list' : 'print, len…'}
              onChange={(v) => at((x) => void (x.allowed_builtins = v))}
            />
            <Switch size="sm" label="Use an allow-list" checked={c.allowed_builtins !== null} onCheckedChange={(v) => at((x) => void (x.allowed_builtins = v ? [] : null))} />
          </div>
          <div className="space-y-1.5">
            <ChipInput
              label="Allowed imports"
              values={c.allowed_imports ?? []}
              normalize={normalizeName}
              disabled={c.allowed_imports === null}
              placeholder={c.allowed_imports === null ? 'Any import allowed' : 'No import allowed'}
              onChange={(v) => at((x) => void (x.allowed_imports = v))}
            />
            <Switch size="sm" label="Restrict imports" checked={c.allowed_imports !== null} onCheckedChange={(v) => at((x) => void (x.allowed_imports = v ? [] : null))} />
          </div>
          <ChipInput label="Forbidden methods" tone="fail" values={c.forbidden_methods} normalize={normalizeName} placeholder="sort, join…" onChange={(v) => at((x) => void (x.forbidden_methods = v))} />
          <div className="sm:col-span-2">
            <ConstructPicker label="Forbidden constructs" values={c.forbidden_constructs} onChange={(v) => at((x) => void (x.forbidden_constructs = v))} />
          </div>
          <div className="sm:col-span-2">
            <ConstructPicker label="Required constructs" values={c.required_constructs} onChange={(v) => at((x) => void (x.required_constructs = v))} />
          </div>
        </div>
      )}
      {!c && <Badge>Uses the global constraints</Badge>}
    </section>
  )
}
