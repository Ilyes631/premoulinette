import { Languages, RotateCcw, RotateCw, Save, Settings2 } from 'lucide-react'
import { useId, useState } from 'react'
import { DemoReadOnlyNotice } from '@/components/demo/read-only-notice'
import { Button, EmptyState, Input, Skeleton } from '@/components/ui'
import { AiSection } from '@/features/settings/ai-section'
import { FieldError, RadioCards, SettingsSection } from '@/features/settings/parts'
import { SandboxSection } from '@/features/settings/sandbox-section'
import {
  buildUpdate,
  draftProblems,
  TIMEOUT_MAX_S,
  TIMEOUT_MIN_S,
  toDraft,
  type SettingsDraft,
} from '@/features/settings/settings-form'
import { errorMessage, isApiError } from '@/lib/api'
import { IS_DEMO } from '@/lib/demo/config'
import { toastDemoReadOnly } from '@/lib/demo/notify'
import { useSettings, useUpdateSettings } from '@/lib/queries'
import { toast } from '@/lib/toast'
import type { ExplanationLanguage, Settings } from '@/lib/types'

export function SettingsPage() {
  const query = useSettings()
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Settings</h1>
        <p className="mt-1 text-sm text-fg-muted">Everything stays on this machine. Saved in the local PréMoulinette data folder.</p>
      </div>
      {IS_DEMO && <DemoReadOnlyNotice action="Saving settings" />}
      {query.isPending ? (
        <div className="space-y-4" aria-busy aria-label="Loading the settings">
          <Skeleton className="h-72" />
          <Skeleton className="h-64" />
        </div>
      ) : query.isError ? (
        <EmptyState icon={Settings2} tone="fail" title="The settings could not be loaded" description={errorMessage(query.error)}>
          <Button onClick={() => void query.refetch()}>
            <RotateCw aria-hidden /> Retry
          </Button>
        </EmptyState>
      ) : (
        <SettingsForm saved={query.data} />
      )}
    </div>
  )
}

type FieldErrors = Partial<Record<keyof SettingsDraft, string>>

function SettingsForm({ saved }: { saved: Settings }) {
  const update = useUpdateSettings()
  const [draft, setDraft] = useState<SettingsDraft>(() => toDraft(saved))
  const [base, setBase] = useState(saved)
  const [apiKey, setApiKey] = useState('')
  const [serverErrors, setServerErrors] = useState<FieldErrors>({})
  const [showProblems, setShowProblems] = useState(false)
  const timeoutId = useId()

  // New settings from the server (after a save): restart from them.
  if (base !== saved) {
    setBase(saved)
    setDraft(toDraft(saved))
  }

  const patch = buildUpdate(saved, draft, apiKey)
  const dirty = Object.keys(patch).length > 0
  const problems = draftProblems(draft)
  const errors: FieldErrors = { ...serverErrors }
  for (const p of problems) if (showProblems || p.field === 'local_mode_acknowledged') errors[p.field] ??= p.message
  const blocked = problems.length > 0

  const onChange = (next: Partial<SettingsDraft>) => {
    setDraft((d) => ({ ...d, ...next }))
    setServerErrors({})
  }

  const submit = async (body = patch, successTitle = 'Settings saved') => {
    setShowProblems(true)
    if (blocked) return
    try {
      await update.mutateAsync(body)
      setApiKey('')
      setServerErrors({})
      toast({ title: successTitle, tone: 'success' })
    } catch (error) {
      if (toastDemoReadOnly(error)) return
      if (isApiError(error) && error.validationErrors.length) {
        const fieldErrors: FieldErrors = {}
        for (const item of error.validationErrors) {
          const field = item.loc[item.loc.length - 1]
          if (typeof field === 'string') fieldErrors[field as keyof SettingsDraft] = item.msg
        }
        setServerErrors(fieldErrors)
      }
      toast({ title: 'Settings not saved', description: errorMessage(error), tone: 'error' })
    }
  }

  const removeKey = () => submit({ anthropic_api_key: null }, 'API key removed')

  return (
    <form
      className="space-y-4 pb-20"
      onSubmit={(e) => {
        e.preventDefault()
        void submit()
      }}
    >
      <SandboxSection draft={draft} onChange={onChange} errors={errors} />
      <AiSection
        saved={saved}
        draft={draft}
        onChange={onChange}
        apiKey={apiKey}
        onApiKey={setApiKey}
        onRemoveKey={() => void removeKey()}
        removingKey={update.isPending && update.variables?.anthropic_api_key === null}
        errors={errors}
      />
      <SettingsSection id="general" icon={Languages} title="Explanations & tests" description="Language of the explanations and default limits of the generated tests.">
        <RadioCards<ExplanationLanguage>
          name="explanation_language"
          legend="Explanation language"
          columns={2}
          value={draft.explanation_language}
          onChange={(v) => onChange({ explanation_language: v })}
          options={[
            { value: 'fr', title: 'Français', description: 'Explications et correctifs en français.' },
            { value: 'en', title: 'English', description: 'Explanations and fixes in English.' },
          ]}
        />
        <div className="max-w-xs">
          <label htmlFor={timeoutId} className="mb-1.5 block text-xs font-medium text-fg-muted">
            Default timeout per test
          </label>
          <div className="flex items-center gap-2">
            <Input
              id={timeoutId}
              type="number"
              inputMode="decimal"
              min={TIMEOUT_MIN_S}
              max={TIMEOUT_MAX_S}
              step={0.5}
              value={Number.isNaN(draft.default_timeout_s) ? '' : draft.default_timeout_s}
              invalid={Boolean(errors.default_timeout_s)}
              onChange={(e) => onChange({ default_timeout_s: e.target.value === '' ? Number.NaN : Number(e.target.value) })}
              className="tabular w-28"
            />
            <span className="text-sm text-fg-muted">seconds</span>
          </div>
          <FieldError message={errors.default_timeout_s} />
          <p className="mt-1.5 text-xs text-fg-subtle">A test running longer is stopped and reported as a timeout.</p>
        </div>
      </SettingsSection>

      <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-3 rounded-xl border border-border-strong bg-surface/95 px-4 py-3 shadow-pop backdrop-blur">
        <p className="text-sm text-fg-muted" aria-live="polite">
          {blocked && draft.sandbox_mode === 'local' && !draft.local_mode_acknowledged
            ? 'Acknowledge the Developer mode risks to save.'
            : dirty
              ? 'You have unsaved changes.'
              : 'All changes saved.'}
        </p>
        <div className="ml-auto flex gap-2">
          {dirty && (
            <Button
              variant="ghost"
              onClick={() => {
                setDraft(toDraft(saved))
                setApiKey('')
                setServerErrors({})
                setShowProblems(false)
              }}
            >
              <RotateCcw aria-hidden /> Discard
            </Button>
          )}
          <Button type="submit" variant="primary" disabled={!dirty || blocked} loading={update.isPending}>
            <Save aria-hidden /> Save settings
          </Button>
        </div>
      </div>
    </form>
  )
}
