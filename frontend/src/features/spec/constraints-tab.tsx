import { Pencil, RotateCcw, Save } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, ProvenanceBadge, Switch } from '@/components/ui'
import type { Constraints, PracticalSpec } from '@/lib/types'
import { ConstructPicker } from './construct-picker'
import { ChipInput, SectionTitle } from './parts'
import { cloneSpec, normalizeName, userOrigin } from './spec-utils'

export interface ConstraintsTabProps {
  spec: PracticalSpec
  saving: boolean
  onSave: (spec: PracticalSpec) => Promise<boolean>
  onEditExercise: (index: number) => void
}

export function ConstraintsTab({ spec, saving, onSave, onEditExercise }: ConstraintsTabProps) {
  const [draft, setDraft] = useState<Constraints>(() => cloneSpec(spec.global_constraints))
  const [base, setBase] = useState(spec.global_constraints)
  // A new spec from the server (save, reparse) resets the draft.
  if (base !== spec.global_constraints) {
    setBase(spec.global_constraints)
    setDraft(cloneSpec(spec.global_constraints))
  }
  const dirty = JSON.stringify(draft) !== JSON.stringify(spec.global_constraints)
  const set = (patch: Partial<Constraints>) => setDraft((d) => ({ ...d, ...patch }))

  const save = () => onSave({ ...spec, global_constraints: { ...draft, origin: userOrigin(draft.origin) } })
  const overrides = spec.exercises.map((ex, i) => ({ ex, i })).filter(({ ex }) => ex.constraints)

  const importsPolicy =
    draft.allowed_imports === null
      ? 'Any import is allowed (except the forbidden ones).'
      : draft.allowed_imports.length === 0
        ? 'No import is allowed.'
        : `Only these modules may be imported: ${draft.allowed_imports.join(', ')}.`

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3.5">
          <h3 className="text-sm font-semibold text-fg">Global constraints</h3>
          <ProvenanceBadge provenance={spec.global_constraints.origin.provenance} confidence={spec.global_constraints.origin.confidence} />
          <span className="text-xs text-fg-muted">Apply to every exercise without its own constraints.</span>
          <div className="ml-auto flex gap-2">
            {dirty && (
              <Button size="sm" variant="ghost" onClick={() => setDraft(cloneSpec(spec.global_constraints))}>
                <RotateCcw aria-hidden /> Discard
              </Button>
            )}
            <Button size="sm" variant="primary" disabled={!dirty} loading={saving} onClick={save}>
              <Save aria-hidden /> Save constraints
            </Button>
          </div>
        </div>
        <div className="grid gap-5 px-5 py-5 md:grid-cols-2">
          <div className="space-y-1.5">
            <ChipInput
              label="Allowed builtins"
              tone="pass"
              values={draft.allowed_builtins ?? []}
              normalize={normalizeName}
              disabled={draft.allowed_builtins === null}
              placeholder={draft.allowed_builtins === null ? 'No allow-list: every builtin not forbidden is allowed' : 'Type a builtin and press Enter'}
              onChange={(v) => set({ allowed_builtins: v })}
            />
            <Switch
              size="sm"
              label="Only allow the builtins listed above"
              checked={draft.allowed_builtins !== null}
              onCheckedChange={(v) => set({ allowed_builtins: v ? [] : null })}
            />
          </div>
          <ChipInput
            label="Forbidden builtins"
            tone="fail"
            values={draft.forbidden_builtins}
            normalize={normalizeName}
            placeholder="abs, max, eval…"
            onChange={(v) => set({ forbidden_builtins: v })}
          />
          <div className="space-y-1.5">
            <ChipInput
              label="Allowed imports"
              values={draft.allowed_imports ?? []}
              normalize={normalizeName}
              disabled={draft.allowed_imports === null}
              placeholder={draft.allowed_imports === null ? 'Any import allowed' : 'No import allowed'}
              onChange={(v) => set({ allowed_imports: v })}
            />
            <Switch
              size="sm"
              label="Restrict imports"
              checked={draft.allowed_imports !== null}
              onCheckedChange={(v) => set({ allowed_imports: v ? [] : null })}
            />
            <p className="text-xs text-fg-muted">{importsPolicy}</p>
          </div>
          <ChipInput
            label="Forbidden imports"
            tone="fail"
            values={draft.forbidden_imports}
            normalize={normalizeName}
            placeholder="os, sys…"
            onChange={(v) => set({ forbidden_imports: v })}
          />
          <ChipInput
            label="Forbidden methods"
            tone="fail"
            values={draft.forbidden_methods}
            normalize={normalizeName}
            placeholder="sort, join…"
            onChange={(v) => set({ forbidden_methods: v })}
          />
          <div />
          <div className="md:col-span-2">
            <ConstructPicker label="Forbidden constructs" values={draft.forbidden_constructs} onChange={(v) => set({ forbidden_constructs: v })} />
          </div>
          <div className="md:col-span-2">
            <ConstructPicker label="Required constructs" values={draft.required_constructs} onChange={(v) => set({ required_constructs: v })} />
          </div>
        </div>
      </Card>

      <Card>
        <div className="px-5 py-4">
          <SectionTitle>Per-exercise overrides</SectionTitle>
          {overrides.length === 0 ? (
            <p className="text-sm text-fg-subtle">Every exercise uses the global constraints.</p>
          ) : (
            <ul className="divide-y divide-border">
              {overrides.map(({ ex, i }) => (
                <li key={ex.id} className="flex flex-wrap items-center gap-2 py-2.5">
                  <span className="text-sm font-medium text-fg">{ex.title}</span>
                  <code className="font-mono text-2xs text-fg-subtle">{ex.file_path}</code>
                  <span className="flex flex-wrap gap-1">
                    {ex.constraints?.forbidden_builtins.map((b) => (
                      <Badge key={b} tone="fail" className="font-mono">
                        {b}
                      </Badge>
                    ))}
                  </span>
                  <Button size="sm" variant="ghost" className="ml-auto" onClick={() => onEditExercise(i)} aria-label={`Edit constraints of ${ex.title}`}>
                    <Pencil aria-hidden /> Edit
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  )
}
