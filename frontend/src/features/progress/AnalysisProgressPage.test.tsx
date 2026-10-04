import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeJob, renderRoute } from '@/features/home/test-utils'
import { rememberJob } from '@/features/progress/job-context'
import { parseServerDate } from '@/features/progress/use-elapsed'
import { api, ApiError } from '@/lib/api'
import { AnalysisProgressPage } from '@/pages/AnalysisProgressPage'

const route = { path: '/jobs/:id', url: '/jobs/job-1' }

describe('AnalysisProgressPage', () => {
  it('renders every stage of a running job with progress and names', async () => {
    rememberJob('job-1', {
      subject_id: 's1',
      project_id: 'p1',
      subject_title: 'TP 1 — MysteryInc',
      project_name: 'mysteryinc_buggy',
    })
    const getJob = vi.spyOn(api, 'getJob').mockResolvedValue(makeJob())
    renderRoute(<AnalysisProgressPage />, route)

    const list = await screen.findByRole('list', { name: 'Analysis stages' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(7)
    expect(items.map((li) => li.getAttribute('data-status'))).toEqual([
      'done',
      'done',
      'running',
      'pending',
      'pending',
      'pending',
      'pending',
    ])
    expect(items[2]).toHaveAttribute('aria-current', 'step')
    expect(items[2]).toHaveTextContent('Compiling Python files…')
    expect(screen.getByRole('progressbar', { name: 'Analysis progress' })).toHaveAttribute('aria-valuenow', '42')
    expect(screen.getByText('2 of 7 stages')).toBeInTheDocument()
    expect(screen.getByText('TP 1 — MysteryInc · mysteryinc_buggy')).toBeInTheDocument()
    expect(screen.getByRole('timer')).toBeInTheDocument()
    expect(getJob).toHaveBeenCalledWith('job-1', expect.anything())
  })

  it('opens the report when the job is done', async () => {
    vi.spyOn(api, 'getJob').mockResolvedValue(
      makeJob({
        status: 'done',
        progress: 1,
        result_id: 'rep-1',
        stages: makeJob().stages.map((s) => ({ ...s, status: 'done' as const })),
      }),
    )
    renderRoute(<AnalysisProgressPage />, route)
    expect(await screen.findByTestId('location')).toHaveTextContent('/analyses/rep-1')
  })

  it('shows the failure with retry and settings actions', async () => {
    const user = userEvent.setup()
    rememberJob('job-1', { subject_id: 's1', project_id: 'p1' })
    vi.spyOn(api, 'getJob').mockResolvedValue(
      makeJob({
        status: 'error',
        error: 'Docker is not available. Enable Developer mode in Settings to run locally.',
        finished_at: new Date().toISOString(),
        stages: makeJob().stages.map((s) =>
          s.key === 'compile' ? { ...s, status: 'error' as const } : s.status === 'running' ? { ...s, status: 'pending' as const } : s,
        ),
      }),
    )
    const start = vi.spyOn(api, 'startAnalysis').mockResolvedValue({ job_id: 'job-2' })
    renderRoute(<AnalysisProgressPage />, route)

    expect(await screen.findByRole('heading', { name: 'Analysis failed' })).toBeInTheDocument()
    expect(screen.getByText(/Docker is not available/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open settings/i })).toHaveAttribute('href', '/settings')
    expect(screen.getByRole('link', { name: /back home/i })).toHaveAttribute('href', '/')

    await user.click(screen.getByRole('button', { name: /retry analysis/i }))
    await waitFor(() => expect(start).toHaveBeenCalledWith({ subject_id: 's1', project_id: 'p1' }))
  })

  it('hides "Open settings" for unrelated errors', async () => {
    vi.spyOn(api, 'getJob').mockResolvedValue(makeJob({ status: 'error', error: 'Subject has no exercise.' }))
    renderRoute(<AnalysisProgressPage />, route)
    expect(await screen.findByText('Subject has no exercise.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /open settings/i })).not.toBeInTheDocument()
  })

  it('explains an unknown job', async () => {
    vi.spyOn(api, 'getJob').mockRejectedValue(new ApiError(404, "Unknown job 'job-1'"))
    renderRoute(<AnalysisProgressPage />, route)
    expect(await screen.findByText('Analysis job not found')).toBeInTheDocument()
  })
})

describe('parseServerDate', () => {
  it('accepts Python microsecond timestamps', () => {
    expect(parseServerDate('2026-10-04T10:00:00.123456+00:00')).toBe(Date.parse('2026-10-04T10:00:00.123Z'))
    expect(parseServerDate(null)).toBeNull()
    expect(parseServerDate('nope')).toBeNull()
  })
})
