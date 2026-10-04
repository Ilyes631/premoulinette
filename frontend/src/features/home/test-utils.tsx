/** Shared helpers for the home / progress page tests (rendering + API fixtures). */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ThemeProvider } from '@/components/providers/theme-provider'
import { TooltipProvider } from '@/components/ui'
import type { Health, JobState, ProjectView, SubjectView } from '@/lib/types'
import { demoSpec, demoSpecStats } from '@/mocks/generated/demo-spec'

export function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

/** Renders `element` at `path` (route pattern) inside every provider the pages need. */
export function renderRoute(element: ReactElement, { path = '/', url = '/' }: { path?: string; url?: string } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } },
  })
  const utils = render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <TooltipProvider>
          <MemoryRouter initialEntries={[url]}>
            <Routes>
              <Route path={path} element={element} />
              <Route path="*" element={<LocationProbe />} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
  return { ...utils, client }
}

export function makeHealth(overrides: Partial<Health> = {}): Health {
  return {
    ok: true,
    version: '0.1.0',
    python: '3.14.0',
    docker: { available: true, version: '27.0', image: 'python:3.12-slim', image_ready: true, error: null },
    sandbox_mode: 'auto',
    sandbox_mode_effective: 'docker',
    sandbox_note: 'Docker sandbox (python:3.12-slim).',
    ai: { configured: false, enabled: false },
    ...overrides,
  }
}

export function makeSubjectView(overrides: Partial<SubjectView> = {}): SubjectView {
  return {
    id: 'subj-1',
    title: 'TP 1 — MysteryInc: First Launch',
    source_name: 'subject_demo.html',
    created_at: '2026-10-04T10:00:00Z',
    updated_at: '2026-10-04T10:00:00Z',
    parser: 'heuristic',
    media_type: 'html',
    spec: demoSpec,
    stats: demoSpecStats,
    warnings: [],
    validation: [],
    ...overrides,
  }
}

export function makeProjectView(overrides: Partial<ProjectView> = {}): ProjectView {
  return {
    id: 'proj-1',
    name: 'mysteryinc_buggy',
    source_kind: 'path',
    source_path: 'C:\\Users\\me\\tp1',
    created_at: '2026-10-04T10:00:00Z',
    file_count: 14,
    python_files: 11,
    tree: [],
    git: {
      is_repo: true,
      branch: 'main',
      head: 'abc1234def',
      last_commit_message: 'init',
      last_commit_date: null,
      dirty: true,
      modified: ['kelvin.py'],
      untracked: ['notes.txt'],
      staged: [],
      ignored_required: [],
      remote_url: null,
      tags: [],
      error: null,
    },
    language: 'python',
    warnings: [],
    ...overrides,
  }
}

export function makeJob(overrides: Partial<JobState> = {}): JobState {
  return {
    id: 'job-1',
    kind: 'analysis',
    status: 'running',
    stage: 'compile',
    stages: [
      { key: 'subject', label: 'Parsing subject…', status: 'done' },
      { key: 'repository', label: 'Inspecting repository…', status: 'done' },
      { key: 'compile', label: 'Compiling Python files…', status: 'running' },
      { key: 'explicit', label: 'Running explicit tests…', status: 'pending' },
      { key: 'derived', label: 'Running derived tests…', status: 'pending' },
      { key: 'constraints', label: 'Checking constraints…', status: 'pending' },
      { key: 'report', label: 'Building report…', status: 'pending' },
    ],
    progress: 0.42,
    result_id: null,
    error: null,
    created_at: new Date().toISOString(),
    finished_at: null,
    ...overrides,
  }
}
