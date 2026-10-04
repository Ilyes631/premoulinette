import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderRoute } from '@/features/home/test-utils'
import { api } from '@/lib/api'
import type { AnalysisListItem } from '@/lib/types'
import { HistoryPage } from '@/pages/HistoryPage'
import { formatDelta, groupAnalyses } from './history-utils'

function item(overrides: Partial<AnalysisListItem> & Pick<AnalysisListItem, 'id' | 'number' | 'created_at'>): AnalysisListItem {
  return {
    subject_id: 's1',
    project_id: 'p1',
    subject_title: 'TP 1 — MysteryInc',
    project_name: 'mysteryinc_buggy',
    readiness: 50,
    mandatory_readiness: 50,
    bonus_completion: null,
    verdict: 'not_ready',
    mandatory_failures: 3,
    ...overrides,
  }
}

const ITEMS: AnalysisListItem[] = [
  item({ id: 'a3', number: 3, created_at: '2026-10-04T12:00:00Z', readiness: 100, verdict: 'ready', mandatory_failures: 0 }),
  item({ id: 'a1', number: 1, created_at: '2026-10-04T10:00:00Z', readiness: 40 }),
  item({ id: 'a2', number: 2, created_at: '2026-10-04T11:00:00Z', readiness: 72.5 }),
  item({ id: 'b1', number: 1, created_at: '2026-10-03T09:00:00Z', project_id: 'p2', project_name: 'other', readiness: 80 }),
]

describe('groupAnalyses', () => {
  it('groups by subject and project, chronologically, with deltas', () => {
    const groups = groupAnalyses(ITEMS)
    expect(groups.map((g) => g.key)).toEqual(['s1::p1', 's1::p2'])
    const first = groups[0]!
    expect(first.runs.map((r) => r.item.id)).toEqual(['a1', 'a2', 'a3'])
    expect(first.runs.map((r) => r.delta)).toEqual([null, 32.5, 27.5])
    expect(first.latest.item.id).toBe('a3')
    expect(formatDelta(-4)).toBe('−4')
    expect(formatDelta(0)).toBe('±0')
    expect(formatDelta(null)).toBe('first run')
  })
})

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('lists the analyses grouped with trend and links', async () => {
    vi.spyOn(api, 'listAnalyses').mockResolvedValue(ITEMS)
    renderRoute(<HistoryPage />, { path: '/history', url: '/history' })
    const list = await screen.findByRole('list', { name: 'Analyses of mysteryinc_buggy' })
    const links = within(list).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/analyses/a3', '/analyses/a2', '/analyses/a1'])
    expect(screen.getByRole('img', { name: 'Readiness trend: 40%, 72%, 100%' })).toBeInTheDocument()
    expect(within(list).getByText('+27.5')).toBeInTheDocument()
  })

  it('shows an empty state with a call to action', async () => {
    vi.spyOn(api, 'listAnalyses').mockResolvedValue([])
    renderRoute(<HistoryPage />, { path: '/history', url: '/history' })
    expect(await screen.findByText('No analysis yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start an analysis' })).toHaveAttribute('href', '/')
  })
})
