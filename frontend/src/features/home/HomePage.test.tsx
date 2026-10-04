import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { analyzeBlocker, looksAbsolute, normalizePathInput } from '@/features/home/logic'
import { SELECTED_PROJECT_KEY, SELECTED_SUBJECT_KEY } from '@/features/home/selection'
import { recallJob } from '@/features/progress/job-context'
import { api, ApiError } from '@/lib/api'
import type { DiscoveredProject, DiscoverProjectsResult } from '@/lib/types'
import { HomePage } from '@/pages/HomePage'
import { makeHealth, makeProjectView, makeSubjectView, renderRoute } from './test-utils'

function analyzeButton() {
  return screen.getByRole('button', { name: /analyze project/i })
}
const subjectCard = () => screen.getByRole('region', { name: 'Subject' })
const projectCard = () => screen.getByRole('region', { name: 'Student project' })

const noDiscovered: DiscoverProjectsResult = { projects: [], scanned: [], duration_ms: 1 }

function makeDiscovered(overrides: Partial<DiscoveredProject> = {}): DiscoveredProject {
  return {
    path: '\\\\wsl.localhost\\Ubuntu\\root\\epita-prog-101-tp2',
    name: 'epita-prog-101-tp2',
    location: 'wsl',
    distro: 'Ubuntu',
    display_path: 'Ubuntu: /root/epita-prog-101-tp2',
    branch: 'main',
    last_activity: new Date(Date.now() - 2 * 3600_000).toISOString(),
    last_message: 'commit: TP2',
    remote_url: 'git@git.forge.epita.fr:p/tp2.git',
    is_school: true,
    ...overrides,
  }
}

async function openLocalFolderTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(within(projectCard()).getByRole('tab', { name: /local folder/i }))
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getHealth').mockResolvedValue(makeHealth())
    vi.spyOn(api, 'listAnalyses').mockResolvedValue([])
    vi.spyOn(api, 'discoverProjects').mockResolvedValue(noDiscovered)
  })

  it('renders the hero and keeps Analyze disabled until both imports are ready', async () => {
    const user = userEvent.setup()
    const upload = vi.spyOn(api, 'uploadSubject').mockResolvedValue(makeSubjectView())
    const createFromPath = vi.spyOn(api, 'createProjectFromPath').mockResolvedValue(makeProjectView())
    const start = vi.spyOn(api, 'startAnalysis').mockResolvedValue({ job_id: 'job-9' })

    renderRoute(<HomePage />)

    expect(screen.getByRole('heading', { level: 1, name: 'PréMoulinette' })).toBeInTheDocument()
    expect(screen.getByText('Test your project before the real submission.')).toBeInTheDocument()
    expect(analyzeButton()).toBeDisabled()
    expect(screen.getByText('Import a subject and a student project to start.')).toBeInTheDocument()

    // 1. subject
    const file = new File(['<h1>TP</h1>'], 'subject.html', { type: 'text/html' })
    await user.upload(screen.getByLabelText('Subject file'), file)
    expect(upload).toHaveBeenCalledWith(file)
    expect(await within(subjectCard()).findByText('TP 1 — MysteryInc: First Launch')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /review extracted requirements/i })).toHaveAttribute('href', '/subjects/subj-1')
    expect(screen.getByTestId('subject-validity')).toHaveTextContent('no validation issues')
    expect(analyzeButton()).toBeDisabled()
    expect(screen.getByText('Import your student project to start.')).toBeInTheDocument()

    // 2. project from a local folder (quotes from "Copy as path" are stripped)
    await openLocalFolderTab(user)
    await user.type(screen.getByLabelText('Absolute path of your project folder'), '"C:\\Users\\me\\tp1"')
    await user.click(screen.getByRole('button', { name: 'Use folder' }))
    expect(createFromPath).toHaveBeenCalledWith('C:\\Users\\me\\tp1')
    expect(await within(projectCard()).findByText('mysteryinc_buggy')).toBeInTheDocument()
    const gitStatus = screen.getByLabelText('Git status')
    expect(within(gitStatus).getByText('main')).toBeInTheDocument()
    expect(within(gitStatus).getByText('1 untracked')).toBeInTheDocument()

    await waitFor(() => expect(analyzeButton()).toBeEnabled())
    expect(window.localStorage.getItem(SELECTED_SUBJECT_KEY)).toBe('subj-1')
    expect(window.localStorage.getItem(SELECTED_PROJECT_KEY)).toBe('proj-1')

    await user.click(analyzeButton())
    expect(start).toHaveBeenCalledWith({ subject_id: 'subj-1', project_id: 'proj-1' })
    expect(await screen.findByTestId('location')).toHaveTextContent('/jobs/job-9')
    expect(recallJob('job-9')).toMatchObject({
      subject_id: 'subj-1',
      project_id: 'proj-1',
      subject_title: 'TP 1 — MysteryInc: First Launch',
      project_name: 'mysteryinc_buggy',
    })
  })

  it('rejects an unsupported subject file and a relative path without calling the API', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const upload = vi.spyOn(api, 'uploadSubject')
    const createFromPath = vi.spyOn(api, 'createProjectFromPath')
    renderRoute(<HomePage />)

    await user.upload(screen.getByLabelText('Subject file'), new File(['x'], 'notes.docx'))
    expect(await screen.findByText(/is not a supported subject/)).toBeInTheDocument()

    await openLocalFolderTab(user)
    await user.type(screen.getByLabelText('Absolute path of your project folder'), 'tp1')
    await user.click(screen.getByRole('button', { name: 'Use folder' }))
    expect(await screen.findByText(/is not an absolute path/)).toBeInTheDocument()

    expect(upload).not.toHaveBeenCalled()
    expect(createFromPath).not.toHaveBeenCalled()
    expect(analyzeButton()).toBeDisabled()
  })

  it('shows the server error when the subject upload fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'uploadSubject').mockRejectedValue(new ApiError(422, 'No exercise found in this subject.'))
    renderRoute(<HomePage />)
    await user.upload(screen.getByLabelText('Subject file'), new File(['x'], 'subject.md'))
    expect(await screen.findByText('No exercise found in this subject.')).toBeInTheDocument()
    expect(analyzeButton()).toBeDisabled()
  })

  it('loads the buggy demo into both cards and starts with Ctrl+Enter', async () => {
    const user = userEvent.setup()
    const loadDemo = vi
      .spyOn(api, 'loadDemo')
      .mockResolvedValue({ subject: makeSubjectView(), project: makeProjectView({ source_kind: 'demo' }) })
    const start = vi.spyOn(api, 'startAnalysis').mockResolvedValue({ job_id: 'job-demo' })

    renderRoute(<HomePage />)
    await user.click(screen.getByRole('button', { name: /load demo project/i }))
    expect(loadDemo).toHaveBeenCalledWith('buggy')
    await waitFor(() => expect(analyzeButton()).toBeEnabled())
    expect(within(projectCard()).getByText('Demo project')).toBeInTheDocument()

    fireEvent.keyDown(document.body, { key: 'Enter', ctrlKey: true })
    await waitFor(() => expect(start).toHaveBeenCalledWith({ subject_id: 'subj-1', project_id: 'proj-1' }))
    expect(await screen.findByTestId('location')).toHaveTextContent('/jobs/job-demo')
  })

  it('restores the remembered selection from localStorage', async () => {
    window.localStorage.setItem(SELECTED_SUBJECT_KEY, 'subj-7')
    window.localStorage.setItem(SELECTED_PROJECT_KEY, 'proj-7')
    const getSubject = vi
      .spyOn(api, 'getSubject')
      .mockResolvedValue(
        makeSubjectView({
          id: 'subj-7',
          title: 'Remembered subject',
          validation: [{ level: 'error', path: 'exercises[0]', message: 'Exercise without file' }],
        }),
      )
    const getProject = vi.spyOn(api, 'getProject').mockResolvedValue(makeProjectView({ id: 'proj-7', name: 'my-tp' }))

    renderRoute(<HomePage />)
    expect(await within(subjectCard()).findByText('Remembered subject')).toBeInTheDocument()
    expect(await within(projectCard()).findByText('my-tp')).toBeInTheDocument()
    expect(getSubject).toHaveBeenCalledWith('subj-7')
    expect(getProject).toHaveBeenCalledWith('proj-7')
    expect(screen.getByTestId('subject-validity')).toHaveTextContent('1 validation error')
    await waitFor(() => expect(analyzeButton()).toBeEnabled())
  })

  it('forgets a remembered id the server no longer knows', async () => {
    window.localStorage.setItem(SELECTED_SUBJECT_KEY, 'gone')
    vi.spyOn(api, 'getSubject').mockRejectedValue(new ApiError(404, 'Unknown subject'))
    renderRoute(<HomePage />)
    await waitFor(() => expect(window.localStorage.getItem(SELECTED_SUBJECT_KEY)).toBeNull())
    expect(screen.getByLabelText('Subject file')).toBeInTheDocument()
  })

  it('warns when no sandbox is configured and lists recent analyses', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue(
      makeHealth({
        sandbox_mode_effective: 'none',
        sandbox_note: 'Docker is not available. Enable Developer mode in Settings to run locally.',
      }),
    )
    vi.spyOn(api, 'listAnalyses').mockResolvedValue([
      {
        id: 'an-1',
        number: 3,
        created_at: new Date().toISOString(),
        subject_id: 'subj-1',
        project_id: 'proj-1',
        subject_title: 'TP 1',
        project_name: 'mysteryinc_buggy',
        readiness: 62.5,
        mandatory_readiness: 62.5,
        bonus_completion: null,
        verdict: 'not_ready',
        mandatory_failures: 4,
      },
    ])
    renderRoute(<HomePage />)
    expect(await screen.findByText(/no sandbox is ready/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open settings/i })).toHaveAttribute('href', '/settings')
    const row = await screen.findByRole('link', { name: /TP 1/ })
    expect(row).toHaveAttribute('href', '/analyses/an-1')
    expect(within(row).getByText('#3')).toBeInTheDocument()
    expect(within(row).getByText('62%')).toBeInTheDocument()
    expect(within(row).getByText('Not ready')).toBeInTheDocument()
  })
})

describe('My projects tab', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getHealth').mockResolvedValue(makeHealth())
    vi.spyOn(api, 'listAnalyses').mockResolvedValue([])
  })

  it('lists the projects found on the PC with their badges', async () => {
    vi.spyOn(api, 'discoverProjects').mockResolvedValue({
      projects: [
        makeDiscovered(),
        makeDiscovered({
          path: 'C:\\Users\\me\\Documents\\perso',
          name: 'perso',
          location: 'windows',
          distro: null,
          display_path: 'C:\\Users\\me\\Documents\\perso',
          branch: 'dev',
          last_activity: null,
          is_school: false,
        }),
      ],
      scanned: ['Ubuntu: /root', 'C:\\Users\\me'],
      duration_ms: 42,
    })
    renderRoute(<HomePage />)

    expect(within(projectCard()).getByRole('tab', { name: /my projects/i })).toHaveAttribute('aria-selected', 'true')
    const list = await screen.findByRole('list', { name: 'Projects found on this PC' })
    const rows = within(list).getAllByRole('button')
    expect(rows).toHaveLength(2)

    const school = rows[0] as HTMLElement
    expect(within(school).getByText('epita-prog-101-tp2')).toBeInTheDocument()
    expect(within(school).getByText('Ubuntu')).toBeInTheDocument()
    expect(within(school).getByText('School')).toBeInTheDocument()
    expect(within(school).getByText('main')).toBeInTheDocument()
    expect(within(school).getByText('last change 2 hours ago')).toBeInTheDocument()
    expect(within(school).getByText('Ubuntu: /root/epita-prog-101-tp2')).toBeInTheDocument()

    const perso = rows[1] as HTMLElement
    expect(within(perso).getByText('Windows')).toBeInTheDocument()
    expect(within(perso).queryByText('School')).not.toBeInTheDocument()
    expect(within(perso).queryByText(/last change/)).not.toBeInTheDocument()
  })

  it('imports a project with one click, like the Local folder flow', async () => {
    const user = userEvent.setup()
    const found = makeDiscovered()
    vi.spyOn(api, 'discoverProjects').mockResolvedValue({ projects: [found], scanned: [], duration_ms: 1 })
    const createFromPath = vi
      .spyOn(api, 'createProjectFromPath')
      .mockResolvedValue(makeProjectView({ name: 'epita-prog-101-tp2', source_path: found.path }))
    renderRoute(<HomePage />)

    await user.click(await screen.findByRole('button', { name: /epita-prog-101-tp2/ }))
    expect(createFromPath).toHaveBeenCalledWith(found.path)
    expect(await within(projectCard()).findByText('Snapshot ready')).toBeInTheDocument()
    expect(window.localStorage.getItem(SELECTED_PROJECT_KEY)).toBe('proj-1')
  })

  it('shows the first 6 projects and a Show all toggle', async () => {
    const user = userEvent.setup()
    const projects = Array.from({ length: 8 }, (_, i) =>
      makeDiscovered({ path: `C:\\tp${i}`, name: `tp${i}`, location: 'windows', distro: null }),
    )
    vi.spyOn(api, 'discoverProjects').mockResolvedValue({ projects, scanned: [], duration_ms: 1 })
    renderRoute(<HomePage />)

    const list = await screen.findByRole('list', { name: 'Projects found on this PC' })
    expect(within(list).getAllByRole('button')).toHaveLength(6)
    await user.click(screen.getByRole('button', { name: 'Show all (2 more)' }))
    expect(within(list).getAllByRole('button')).toHaveLength(8)
  })

  it('switches to the Local folder tab when nothing is found', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'discoverProjects').mockResolvedValue(noDiscovered)
    renderRoute(<HomePage />)

    expect(await screen.findByText('No project found automatically.')).toBeInTheDocument()
    expect(screen.getByText('wslpath -w .')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Use the Local folder tab' }))
    expect(within(projectCard()).getByRole('tab', { name: /local folder/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Absolute path of your project folder')).toBeInTheDocument()
  })

  it('reports a failed search and retries with refresh=1', async () => {
    const user = userEvent.setup()
    const discover = vi
      .spyOn(api, 'discoverProjects')
      .mockRejectedValueOnce(new ApiError(500, 'Scan failed'))
      .mockResolvedValue({ projects: [makeDiscovered()], scanned: [], duration_ms: 1 })
    renderRoute(<HomePage />)

    expect(await screen.findByText('Could not look for your projects.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('button', { name: /epita-prog-101-tp2/ })).toBeInTheDocument()
    expect(discover).toHaveBeenLastCalledWith(true, expect.anything())
  })
})

describe('path helpers', () => {
  it('normalizes quoted Windows paths and detects absolute paths', () => {
    expect(normalizePathInput('  "C:\\a b\\tp"  ')).toBe('C:\\a b\\tp')
    expect(looksAbsolute('C:\\x')).toBe(true)
    expect(looksAbsolute('C:/x')).toBe(true)
    expect(looksAbsolute('/home/me/tp')).toBe(true)
    expect(looksAbsolute('\\\\server\\share')).toBe(true)
    expect(looksAbsolute('tp1')).toBe(false)
    expect(looksAbsolute('.\\tp1')).toBe(false)
  })

  it('explains why Analyze is disabled', () => {
    expect(analyzeBlocker('ready', 'ready')).toBeNull()
    expect(analyzeBlocker('ready', 'uploading')).toBe('Waiting for the import to finish…')
    expect(analyzeBlocker('error', 'ready')).toBe('Import a subject to start.')
    expect(analyzeBlocker('ready', 'empty')).toBe('Import your student project to start.')
  })
})
