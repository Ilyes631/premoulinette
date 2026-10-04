import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '@/lib/api'
import type { Health } from '@/lib/types'
import { ResultsPage } from '@/pages/ResultsPage'
import { makeListItem, makeReport, REPORT_ID } from './testing/mock-report'
import { renderResults } from './testing/render'

const HEALTH: Health = {
  ok: true,
  version: '0.1.0',
  python: '3.14.0',
  docker: { available: true, version: '27', image: 'python:3.12-slim', image_ready: true, error: null },
  sandbox_mode_effective: 'docker',
  ai: { configured: false, enabled: false },
}

const enc = encodeURIComponent

beforeEach(() => {
  vi.spyOn(api, 'getHealth').mockResolvedValue(HEALTH)
})

describe('ResultsPage', () => {
  it('renders the NOT READY verdict and the readiness score from the report', async () => {
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(makeReport())
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}`)

    const verdict = await screen.findByRole('status', { name: /verdict/i })
    expect(verdict).toHaveTextContent('DO NOT SUBMIT YET')
    expect(verdict).toHaveTextContent('2 mandatory failures remain.')
    expect(verdict).toHaveAttribute('data-verdict', 'not_ready')
    expect(screen.getByTestId('readiness-value')).toHaveTextContent('96.4%')
    expect(screen.getByRole('heading', { name: 'TP 1 — MysteryInc: First Launch' })).toBeInTheDocument()
    expect(screen.getByText('Analysis #4')).toBeInTheDocument()
    expect(screen.getByText('Safe mode · Docker')).toBeInTheDocument()
    // overview content
    expect(screen.getByText('53 / 55')).toBeInTheDocument()
    expect(screen.getByText('1 / 4')).toBeInTheDocument()
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.getByText(/Impact on mandatory score: none/)).toBeInTheDocument()
    expect(screen.getByText('3 files are not tracked by Git')).toBeInTheDocument()
    // the critical forbidden builtin comes first in "Fix these first"
    const top = screen.getByRole('region', { name: 'Fix these first' })
    expect(within(within(top).getByRole('list')).getAllByRole('button')[0]).toHaveTextContent('Forbidden builtin abs() used')
  })

  it('renders READY with the hidden-tests warning', async () => {
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(
      makeReport({
        score: {
          verdict: 'ready',
          mandatory_failures: 0,
          readiness: 100,
          verdict_message: 'All requirements that could be verified from the subject passed.',
        },
      }),
    )
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}`)
    const verdict = await screen.findByRole('status', { name: /verdict/i })
    expect(verdict).toHaveTextContent('READY TO SUBMIT')
    expect(verdict).toHaveTextContent('Hidden grader tests may still exist.')
    expect(screen.getByTestId('readiness-value')).toHaveTextContent('100.0%')
  })

  it('groups issues by file with the file score and issue count', async () => {
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(makeReport())
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}/issues`)

    const group = (await screen.findAllByRole('button', { expanded: true })).find((b) =>
      b.textContent?.includes('launch_sequence.py'),
    )
    expect(group).toBeDefined()
    expect(group).toHaveTextContent('92%')
    expect(group).toHaveTextContent('· 2 issues')
    const section = group?.closest('section') as HTMLElement
    expect(within(section).getByText('launch_sequence.py session 1 output')).toBeInTheDocument()
    expect(within(section).getByText('Prompt "Pilot name: "')).toBeInTheDocument()

    // The critical constraint failure group is listed first.
    const groups = document.querySelectorAll('[data-file-group]')
    expect(groups[0]?.getAttribute('data-file-group')).toBe('fuel_share.py')

    // Collapsing hides the rows; info checks are filtered out by default.
    await userEvent.click(group as HTMLElement)
    expect(within(section).queryByText('launch_sequence.py session 1 output')).not.toBeInTheDocument()
    expect(screen.queryByText('Extra file notes.py')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Info/ }))
    expect(screen.getByText('Extra file notes.py')).toBeInTheDocument()
  })

  it('switches tabs through the URL and redirects unknown tabs to the overview', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(makeReport())
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}/nope`)

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(`/analyses/${REPORT_ID}/overview`))
    await user.click(await screen.findByRole('tab', { name: /Tests/ }))
    expect(screen.getByTestId('location')).toHaveTextContent(`/analyses/${REPORT_ID}/tests`)
    expect(screen.getByRole('tab', { name: /Tests/ })).toHaveAttribute('aria-selected', 'true')
    const table = screen.getByRole('table')
    expect(within(table).getByText('is_safe(90, 90)')).toBeInTheDocument()
    expect(within(table).getByText('to_kelvin(-1000)')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /Files/ }))
    expect(screen.getByTestId('location')).toHaveTextContent(`/analyses/${REPORT_ID}/files`)
    expect(screen.getByText('max_altitude.py')).toBeInTheDocument()
  })

  it('shows the check detail with an invisible characters toggle on the diff', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(makeReport())
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}/issues?check=${enc('test:launch_sequence#session1')}`)

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: 'launch_sequence.py session 1 output' })).toBeInTheDocument()
    expect(within(dialog).getByText(/Explicit requirement/)).toBeInTheDocument()
    const countDots = () => (dialog.textContent?.match(/·/g) ?? []).length
    const before = dialog.querySelectorAll('[data-invisible="invisible"]').length
    const dotsBefore = countDots()

    await user.click(within(dialog).getByRole('switch', { name: 'Show invisible characters' }))
    const glyphs = dialog.querySelectorAll('[data-invisible="invisible"]')
    expect(glyphs.length).toBeGreaterThan(before)
    expect([...glyphs].some((g) => g.textContent?.includes('·'))).toBe(true)
    expect(countDots()).toBeGreaterThan(dotsBefore)
    // and back
    await user.click(within(dialog).getByRole('switch', { name: 'Show invisible characters' }))
    expect(dialog.querySelectorAll('[data-invisible="invisible"]')).toHaveLength(before)
  })

  it('explains a check with the offline template and navigates with j/k', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(makeReport())
    const explain = vi.spyOn(api, 'explainCheck').mockResolvedValue({
      title: 'String instead of boolean',
      markdown: 'You returned **"True"** (a string).',
      provider: 'template',
      language: 'en',
      sent_payload: null,
    })
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}/issues`)

    await user.click(await screen.findByRole('button', { name: /landing_grade\(3\.2\) returns True/ }))
    const dialog = await screen.findByRole('dialog')
    expect(screen.getByTestId('location')).toHaveTextContent(`check=${enc('test:landing_grade#ex2')}`)
    expect(within(dialog).getByText('Suggested fix')).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Explain' }))
    expect(explain).toHaveBeenCalledWith(REPORT_ID, 'test:landing_grade#ex2', { mode: 'explain', provider: 'template' })
    expect(await within(dialog).findByText('String instead of boolean')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Ask AI/ })).not.toBeInTheDocument()

    await user.keyboard('j')
    await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent(enc('test:landing_grade#ex2')))
    // the explanation of the previous check is not carried over
    expect(screen.queryByText('String instead of boolean')).not.toBeInTheDocument()
  })

  it('shows the history with a comparison against the previous analysis', async () => {
    vi.spyOn(api, 'getAnalysis').mockResolvedValue(makeReport())
    vi.spyOn(api, 'listAnalyses').mockResolvedValue([
      makeListItem(),
      makeListItem({ id: 'an-3', number: 3, readiness: 90.2, created_at: new Date(Date.now() - 900_000).toISOString() }),
    ])
    const compare = vi.spyOn(api, 'compareAnalyses').mockResolvedValue({
      base_id: 'an-3',
      head_id: REPORT_ID,
      readiness_delta: 6.2,
      fixed: [{ id: 'test:kelvin#ex1', title: 'to_kelvin(0)', file: 'kelvin.py', before: 'fail', after: 'pass' }],
      new_failures: [],
      still_failing: [
        { id: 'test:landing_grade#ex2', title: 'landing_grade(3.2) returns True', file: 'grade_landing.py', before: 'fail', after: 'fail' },
      ],
      new_checks: [],
      removed_checks: [],
    })
    renderResults(<ResultsPage />, `/analyses/${REPORT_ID}/history`)

    expect(await screen.findByText('+1 check fixed')).toBeInTheDocument()
    expect(compare).toHaveBeenCalledWith(REPORT_ID, 'an-3')
    expect(within(screen.getByRole('region', { name: 'Compared with analysis #3' })).getByText('+6.2 pts')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Readiness over 2 analyses/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analysis #3' })).toBeInTheDocument()
  })

  it('shows a not-found state for an unknown analysis', async () => {
    vi.spyOn(api, 'getAnalysis').mockRejectedValue(new ApiError(404, "Unknown analysis 'zzz'"))
    renderResults(<ResultsPage />, '/analyses/zzz')
    expect(await screen.findByText('Analysis not found')).toBeInTheDocument()
  })
})
