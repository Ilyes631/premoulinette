import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeHealth, renderRoute } from '@/features/home/test-utils'
import { api } from '@/lib/api'
import { AppShell } from './AppShell'
import { describeSandbox } from './sandbox-status'

describe('AppShell', () => {
  it('renders the skip link, navigation, sandbox pill and footer', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue(makeHealth())
    renderRoute(<AppShell />, { path: '/history', url: '/history' })

    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main-content')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Analyze' })).not.toHaveAttribute('aria-current')
    expect(await screen.findByRole('link', { name: /Sandbox: Safe mode · Docker/ })).toHaveAttribute('href', '/settings')
    expect(screen.getByText(/Readiness Score is not an official grade/)).toBeInTheDocument()
  })
})

describe('describeSandbox', () => {
  it('maps the effective sandbox mode to a tone', () => {
    expect(describeSandbox(makeHealth()).tone).toBe('pass')
    expect(describeSandbox(makeHealth({ sandbox_mode_effective: 'local' }))).toMatchObject({
      kind: 'local',
      tone: 'warning',
      label: 'Developer mode',
    })
    expect(describeSandbox(makeHealth({ sandbox_mode_effective: 'none', sandbox_note: 'Start Docker.' }))).toMatchObject({
      kind: 'none',
      tone: 'fail',
      label: 'Sandbox not configured',
      description: 'Start Docker.',
    })
    expect(describeSandbox(undefined, { error: true }).kind).toBe('offline')
    expect(describeSandbox(undefined, { loading: true }).kind).toBe('loading')
  })
})
