import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeHealth, makeSubjectView, renderRoute } from '@/features/home/test-utils'
import { api } from '@/lib/api'
import type { PracticalSpec, SubjectTests } from '@/lib/types'
import { SpecReviewPage } from '@/pages/SpecReviewPage'

const EMPTY_TESTS: SubjectTests = { explicit: [], derived: [], heuristic: [], scripts: [] }

function setup() {
  const subject = makeSubjectView()
  vi.spyOn(api, 'getSubject').mockResolvedValue(subject)
  vi.spyOn(api, 'getHealth').mockResolvedValue(makeHealth())
  vi.spyOn(api, 'getSettings').mockRejectedValue(new Error('not needed'))
  vi.spyOn(api, 'getSubjectTests').mockResolvedValue(EMPTY_TESTS)
  vi.spyOn(api, 'getSubjectDocument').mockResolvedValue({ text: 'TP 1', html: null, media_type: 'html' })
  const updateSpec = vi.spyOn(api, 'updateSpec').mockImplementation(async (_id: string, spec: PracticalSpec) => ({ ...subject, spec }))
  renderRoute(<SpecReviewPage />, { path: '/subjects/:id', url: `/subjects/${subject.id}` })
  return { subject, updateSpec }
}

const isCode = (text: string) => (_: string, el: Element | null) => el?.tagName === 'CODE' && el.textContent === text

describe('SpecReviewPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders every exercise with its badges, signatures and rules', async () => {
    setup()
    expect(await screen.findByRole('heading', { name: 'TP 1 — MysteryInc: First Launch' })).toBeInTheDocument()
    expect(screen.getByText('Subject parsed successfully')).toBeInTheDocument()

    const safe = screen.getByTestId('exercise-safe_speed')
    expect(within(safe).getByText('✓ Required')).toBeInTheDocument()
    expect(within(safe).getByText(isCode('def is_safe(speed: int, limit: int) -> bool'))).toBeInTheDocument()
    expect(within(safe).getByText('speed <= limit')).toBeInTheDocument()
    expect(within(safe).getByText('otherwise')).toBeInTheDocument()
    expect(within(safe).getByText('is_safe(200, 250)')).toBeInTheDocument()

    const bonus = screen.getByTestId('exercise-emoji_grade')
    expect(within(bonus).getByText('Bonus')).toBeInTheDocument()
    expect(within(bonus).queryByText('✓ Required')).not.toBeInTheDocument()

    // Script prompts keep their trailing space, rendered visibly.
    const launch = screen.getByTestId('exercise-launch_sequence')
    expect(within(launch).getAllByTitle('1 trailing space').length).toBeGreaterThan(0)
  })

  it('adds a rule in the editor and saves the whole spec with provenance "user"', async () => {
    const user = userEvent.setup()
    const { updateSpec } = setup()
    await user.click(await screen.findByRole('button', { name: 'Edit exercise Exercise 2 — Safe speed' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getAllByTestId('rule-row')).toHaveLength(2)
    await user.click(within(dialog).getByRole('button', { name: 'Add rule to is_safe' }))
    expect(within(dialog).getAllByTestId('rule-row')).toHaveLength(3)

    await user.type(within(dialog).getByLabelText('Rule 3 condition'), 'speed < 0')
    await user.type(within(dialog).getByLabelText('Rule 3 returns'), 'False')
    await user.click(within(dialog).getByRole('button', { name: 'Save exercise' }))

    await waitFor(() => expect(updateSpec).toHaveBeenCalledTimes(1))
    const [id, saved] = updateSpec.mock.calls[0]!
    expect(id).toBe('subj-1')
    const exercise = saved.exercises.find((e) => e.id === 'safe_speed')!
    const rules = exercise.functions[0]!.rules
    expect(rules).toHaveLength(3)
    expect(rules[2]).toMatchObject({ when: 'speed < 0', returns: 'False', origin: { provenance: 'user' } })
    // Untouched items keep their provenance; the rest of the spec is sent unchanged.
    expect(rules[0]!.origin.provenance).toBe('explicit')
    expect(exercise.functions[0]!.tests[0]!.origin.provenance).toBe('explicit')
    expect(saved.exercises).toHaveLength(11)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('blocks saving an incomplete rule client-side', async () => {
    const user = userEvent.setup()
    const { updateSpec } = setup()
    await user.click(await screen.findByRole('button', { name: 'Edit exercise Exercise 2 — Safe speed' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Add rule to is_safe' }))
    await user.click(within(dialog).getByRole('button', { name: 'Save exercise' }))
    expect(await within(dialog).findByText('Rule 3 needs a returned value.')).toBeInTheDocument()
    expect(updateSpec).not.toHaveBeenCalled()
  })

  it('shows server validation errors inline', async () => {
    const user = userEvent.setup()
    setup()
    const { ApiError } = await import('@/lib/api')
    vi.spyOn(api, 'updateSpec').mockRejectedValue(
      new ApiError(422, 'invalid', [{ loc: ['body', 'exercises', 1, 'file_path'], msg: 'path must be relative' }]),
    )
    await user.click(await screen.findByRole('button', { name: 'Edit exercise Exercise 2 — Safe speed' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Save exercise' }))
    expect(await within(dialog).findByText('path must be relative')).toBeInTheDocument()
    expect(within(dialog).getByText('exercises[1].file_path')).toBeInTheDocument()
  })
})
