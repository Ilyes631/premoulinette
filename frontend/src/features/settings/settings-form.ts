import type { Settings, SettingsUpdate } from '@/lib/types'

/** Editable part of the settings (read-only fields stripped). */
export type SettingsDraft = Omit<Settings, 'has_api_key' | 'api_key_source'>

/** Suggestions for the model field (free text: any valid model id is accepted). */
export const MODEL_SUGGESTIONS = ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-4-5']

export const TIMEOUT_MIN_S = 0.5
export const TIMEOUT_MAX_S = 60

export function toDraft(settings: Settings): SettingsDraft {
  return {
    sandbox_mode: settings.sandbox_mode,
    local_mode_acknowledged: settings.local_mode_acknowledged,
    docker_image: settings.docker_image,
    ai_enabled: settings.ai_enabled,
    ai_model: settings.ai_model,
    ai_consent_subject: settings.ai_consent_subject,
    ai_consent_code: settings.ai_consent_code,
    explanation_language: settings.explanation_language,
    default_timeout_s: settings.default_timeout_s,
  }
}

/** Partial PUT body: only changed fields, plus the API key when one was typed (never echoed back). */
export function buildUpdate(saved: Settings, draft: SettingsDraft, apiKey: string): SettingsUpdate {
  const base = toDraft(saved)
  const update: SettingsUpdate = {}
  for (const key of Object.keys(draft) as Array<keyof SettingsDraft>) {
    if (draft[key] !== base[key]) (update as Record<string, unknown>)[key] = draft[key]
  }
  if (apiKey.trim()) update.anthropic_api_key = apiKey.trim()
  return update
}

export interface DraftProblem {
  field: keyof SettingsDraft
  message: string
}

/** Client-side checks mirroring the backend semantic rules. */
export function draftProblems(draft: SettingsDraft): DraftProblem[] {
  const problems: DraftProblem[] = []
  if (draft.sandbox_mode === 'local' && !draft.local_mode_acknowledged)
    problems.push({
      field: 'local_mode_acknowledged',
      message: 'Developer mode needs your explicit acknowledgement of the risks.',
    })
  if (!Number.isFinite(draft.default_timeout_s) || draft.default_timeout_s < TIMEOUT_MIN_S || draft.default_timeout_s > TIMEOUT_MAX_S)
    problems.push({ field: 'default_timeout_s', message: `The timeout must be between ${TIMEOUT_MIN_S} and ${TIMEOUT_MAX_S} seconds.` })
  if (!draft.docker_image.trim()) problems.push({ field: 'docker_image', message: 'The Docker image cannot be empty.' })
  if (draft.ai_enabled && !draft.ai_model.trim()) problems.push({ field: 'ai_model', message: 'Choose a model.' })
  return problems
}
