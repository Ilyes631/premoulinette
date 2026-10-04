import { KeyRound, Lock, Sparkles, Trash2 } from 'lucide-react'
import { useId } from 'react'
import { Badge, Button, Input, Switch } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { Settings } from '@/lib/types'
import { FieldError, SettingsSection } from './parts'
import { MODEL_SUGGESTIONS, type SettingsDraft } from './settings-form'

export interface AiSectionProps {
  saved: Settings
  draft: SettingsDraft
  onChange: (patch: Partial<SettingsDraft>) => void
  apiKey: string
  onApiKey: (value: string) => void
  onRemoveKey: () => void
  removingKey: boolean
  errors: Partial<Record<keyof SettingsDraft, string>>
}

export function AiSection({ saved, draft, onChange, apiKey, onApiKey, onRemoveKey, removingKey, errors }: AiSectionProps) {
  const modelId = useId()
  const keyId = useId()
  const listId = useId()
  const fromEnv = saved.api_key_source === 'env'

  return (
    <SettingsSection
      id="ai"
      icon={Sparkles}
      title="AI explanations (optional)"
      description="Claude can rephrase a failing check or re-parse a subject. It only explains deterministic results — it never decides pass or fail."
    >
      <Switch
        checked={draft.ai_enabled}
        onCheckedChange={(v) => onChange({ ai_enabled: v })}
        label={<span className="text-sm text-fg">Enable AI features</span>}
      />

      <div className={cn('grid gap-4 sm:grid-cols-2', !draft.ai_enabled && 'opacity-60')}>
        <div>
          <label htmlFor={modelId} className="mb-1.5 block text-xs font-medium text-fg-muted">
            Model
          </label>
          <Input
            id={modelId}
            list={listId}
            value={draft.ai_model}
            spellCheck={false}
            invalid={Boolean(errors.ai_model)}
            onChange={(e) => onChange({ ai_model: e.target.value })}
            className="font-mono text-[0.8125rem]"
          />
          <datalist id={listId}>
            {MODEL_SUGGESTIONS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <FieldError message={errors.ai_model} />
        </div>
        <div>
          <label htmlFor={keyId} className="mb-1.5 flex items-center justify-between text-xs font-medium text-fg-muted">
            <span>Anthropic API key</span>
            {saved.has_api_key && (
              <Badge tone="pass">
                <KeyRound aria-hidden /> {fromEnv ? 'From ANTHROPIC_API_KEY' : 'Key saved'}
              </Badge>
            )}
          </label>
          <div className="flex gap-2">
            <Input
              id={keyId}
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              placeholder={saved.has_api_key ? '•••••••• (type to replace)' : 'sk-ant-…'}
              onChange={(e) => onApiKey(e.target.value)}
              className="font-mono text-[0.8125rem]"
              aria-describedby={`${keyId}-help`}
            />
            {saved.has_api_key && !fromEnv && (
              <Button variant="ghost" size="icon" onClick={onRemoveKey} loading={removingKey} aria-label="Remove the saved API key" title="Remove the saved key">
                {!removingKey && <Trash2 aria-hidden />}
              </Button>
            )}
          </div>
          <p id={`${keyId}-help`} className="mt-1.5 flex items-center gap-1 text-xs text-fg-subtle">
            <Lock className="size-3" aria-hidden /> Stored locally, write-only: it is never displayed or sent to the browser again.
          </p>
        </div>
      </div>

      <div className="space-y-3 rounded-lg border border-border bg-surface-2/40 px-4 py-3.5">
        <p className="text-sm font-medium text-fg">What may be sent to Claude</p>
        <p className="text-xs text-pretty text-fg-muted">
          Nothing is sent without your consent. Only the minimal snippet of the failing check is sent, never your
          repository. You can preview the exact payload before every AI explanation.
        </p>
        <Switch
          checked={draft.ai_consent_subject}
          onCheckedChange={(v) => onChange({ ai_consent_subject: v })}
          label={<span className="text-sm text-fg">Send the subject text (for “Re-parse with AI”)</span>}
        />
        <Switch
          checked={draft.ai_consent_code}
          onCheckedChange={(v) => onChange({ ai_consent_code: v })}
          label={<span className="text-sm text-fg">Send minimal code snippets (≤ 25 lines of the failing check)</span>}
        />
      </div>
    </SettingsSection>
  )
}
