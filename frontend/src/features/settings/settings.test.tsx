import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeHealth, renderRoute } from '@/features/home/test-utils'
import { api } from '@/lib/api'
import type { Settings, SettingsUpdate } from '@/lib/types'
import { SettingsPage } from '@/pages/SettingsPage'
import { buildUpdate, draftProblems, toDraft } from './settings-form'

function makeSettings(overrides: Partial<Settings> = {}): Settings {
  return {
    sandbox_mode: 'auto',
    local_mode_acknowledged: false,
    docker_image: 'python:3.12-slim',
    ai_enabled: false,
    ai_model: 'claude-sonnet-5-5',
    ai_consent_subject: false,
    ai_consent_code: false,
    has_api_key: false,
    api_key_source: null,
    explanation_language: 'fr',
    default_timeout_s: 5,
    ...overrides,
  }
}

function setup(settings: Settings = makeSettings()) {
  vi.spyOn(api, 'getSettings').mockResolvedValue(settings)
  vi.spyOn(api, 'getHealth').mockResolvedValue(makeHealth())
  const updateSettings = vi
    .spyOn(api, 'updateSettings')
    .mockImplementation(async (patch: SettingsUpdate) => {
      const { anthropic_api_key, ...rest } = patch
      const hasKey = anthropic_api_key === undefined ? settings.has_api_key : Boolean(anthropic_api_key)
      return { ...settings, ...rest, has_api_key: hasKey }
    })
  renderRoute(<SettingsPage />, { path: '/settings', url: '/settings' })
  return { updateSettings }
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('requires an explicit acknowledgement before enabling Developer mode', async () => {
    const user = userEvent.setup()
    const { updateSettings } = setup()
    await user.click(await screen.findByRole('radio', { name: 'Developer mode' }))

    expect(screen.getByText(/student code will run on your machine with limited isolation/i)).toBeInTheDocument()
    const save = screen.getByRole('button', { name: 'Save settings' })
    expect(save).toBeDisabled()
    expect(screen.getByText('Acknowledge the Developer mode risks to save.')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /I understand the risks/ }))
    expect(save).toBeEnabled()
    await user.click(save)

    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(1))
    expect(updateSettings).toHaveBeenCalledWith({ sandbox_mode: 'local', local_mode_acknowledged: true })
  })

  it('never displays the API key and only sends a newly typed one', async () => {
    const user = userEvent.setup()
    const { updateSettings } = setup(makeSettings({ has_api_key: true, api_key_source: 'settings' }))
    expect(await screen.findByText('Key saved')).toBeInTheDocument()
    const input = screen.getByLabelText(/Anthropic API key/)
    expect(input).toHaveValue('')
    expect(input).toHaveAttribute('type', 'password')

    await user.type(input, '  sk-ant-test  ')
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith({ anthropic_api_key: 'sk-ant-test' }))
    await waitFor(() => expect(input).toHaveValue(''))
  })

  it('shows the privacy promise for AI consents', async () => {
    setup()
    expect(
      await screen.findByText(/Nothing is sent without your consent\. Only the minimal snippet of the failing check is sent, never your repository\./),
    ).toBeInTheDocument()
  })
})

describe('settings form helpers', () => {
  it('builds a minimal partial update', () => {
    const saved = makeSettings()
    const draft = { ...toDraft(saved), explanation_language: 'en' as const }
    expect(buildUpdate(saved, draft, '')).toEqual({ explanation_language: 'en' })
    expect(buildUpdate(saved, toDraft(saved), '')).toEqual({})
  })

  it('flags unacknowledged developer mode and bad timeouts', () => {
    const draft = { ...toDraft(makeSettings()), sandbox_mode: 'local' as const, default_timeout_s: 0 }
    expect(draftProblems(draft).map((p) => p.field)).toEqual(['local_mode_acknowledged', 'default_timeout_s'])
  })
})
