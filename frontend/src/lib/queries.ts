/**
 * React Query hooks over the API client. Every screen should go through these hooks so that
 * caching, polling and invalidation stay consistent. Hooks call `api.*` (not the bare functions)
 * so tests can stub endpoints with `vi.spyOn(api, ...)`.
 */
import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { api, ApiError, type ListAnalysesParams } from './api'
import type {
  DemoVariant,
  ExplainMode,
  ExplainRequest,
  JobState,
  PracticalSpec,
  ProjectView,
  SettingsUpdate,
  StartAnalysisRequest,
  SubjectView,
} from './types'

export const JOB_POLL_INTERVAL_MS = 400
const HEALTH_POLL_INTERVAL_MS = 15_000

export const queryKeys = {
  health: ['health'] as const,
  settings: ['settings'] as const,
  subjects: ['subjects'] as const,
  subject: (id: string) => ['subjects', id] as const,
  subjectTests: (id: string) => ['subjects', id, 'tests'] as const,
  subjectDocument: (id: string) => ['subjects', id, 'document'] as const,
  specSchema: ['spec-schema'] as const,
  projects: ['projects'] as const,
  discoveredProjects: ['discovered-projects'] as const,
  project: (id: string) => ['projects', id] as const,
  projectFile: (id: string, path: string) => ['projects', id, 'file', path] as const,
  job: (id: string) => ['jobs', id] as const,
  analyses: (params: ListAnalysesParams = {}) => ['analyses', 'list', params] as const,
  analysis: (id: string) => ['analyses', 'detail', id] as const,
  comparison: (id: string, baseId: string) => ['analyses', 'compare', id, baseId] as const,
  aiPayload: (analysisId: string, checkId: string, mode: AiPayloadMode) =>
    ['analyses', 'ai-payload', analysisId, checkId, mode] as const,
}

type AiPayloadMode = Exclude<ExplainMode, 'expected'>

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        // Client errors (404, 422...) will not fix themselves: do not retry them.
        retry: (count, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
          return count < 2
        },
      },
      mutations: { retry: false },
    },
  })
}

// ---- health & settings ---------------------------------------------------------------------

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => api.getHealth(signal),
    refetchInterval: HEALTH_POLL_INTERVAL_MS,
    retry: false,
  })
}

export function useSettings() {
  return useQuery({ queryKey: queryKeys.settings, queryFn: () => api.getSettings() })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: SettingsUpdate) => api.updateSettings(patch),
    onSuccess: (settings) => {
      qc.setQueryData(queryKeys.settings, settings)
      void qc.invalidateQueries({ queryKey: queryKeys.health })
    },
  })
}

export function usePrepareSandbox() {
  return useMutation({ mutationFn: () => api.prepareSandbox() })
}

// ---- subjects ------------------------------------------------------------------------------

export function useSubjects() {
  return useQuery({ queryKey: queryKeys.subjects, queryFn: () => api.listSubjects() })
}

export function useSubject(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.subject(id ?? ''),
    queryFn: () => api.getSubject(id as string),
    enabled: Boolean(id),
  })
}

function useStoreSubject() {
  const qc = useQueryClient()
  return (subject: SubjectView) => {
    qc.setQueryData(queryKeys.subject(subject.id), subject)
    void qc.invalidateQueries({ queryKey: queryKeys.subjects, exact: true })
    void qc.invalidateQueries({ queryKey: queryKeys.subjectTests(subject.id) })
  }
}

export function useUploadSubject() {
  const store = useStoreSubject()
  return useMutation({ mutationFn: (file: File) => api.uploadSubject(file), onSuccess: store })
}

export function useReparseSubject(id: string) {
  const store = useStoreSubject()
  return useMutation({ mutationFn: (useAi: boolean) => api.reparseSubject(id, useAi), onSuccess: store })
}

export function useUpdateSpec(id: string) {
  const store = useStoreSubject()
  return useMutation({ mutationFn: (spec: PracticalSpec) => api.updateSpec(id, spec), onSuccess: store })
}

export function useSubjectTests(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.subjectTests(id ?? ''),
    queryFn: () => api.getSubjectTests(id as string),
    enabled: Boolean(id),
  })
}

export function useSubjectDocument(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.subjectDocument(id ?? ''),
    queryFn: () => api.getSubjectDocument(id as string),
    enabled: Boolean(id),
    staleTime: Infinity,
  })
}

export function useSpecSchema() {
  return useQuery({ queryKey: queryKeys.specSchema, queryFn: () => api.getSpecSchema(), staleTime: Infinity })
}

// ---- projects ------------------------------------------------------------------------------

export type ProjectSource =
  | { kind: 'path'; path: string }
  | { kind: 'zip'; file: File }
  | { kind: 'folder'; files: File[]; name?: string }

export function createProject(source: ProjectSource): Promise<ProjectView> {
  switch (source.kind) {
    case 'path':
      return api.createProjectFromPath(source.path)
    case 'zip':
      return api.createProjectFromZip(source.file)
    case 'folder':
      return api.createProjectFromFolder(source.files, source.name)
  }
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      qc.setQueryData(queryKeys.project(project.id), project)
      void qc.invalidateQueries({ queryKey: queryKeys.projects, exact: true })
    },
  })
}

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects, queryFn: () => api.listProjects() })
}

const DISCOVER_STALE_MS = 60_000

/** Git repositories found on this PC (GET /api/projects/discover), cached for a minute. */
export function useDiscoverProjects() {
  return useQuery({
    queryKey: queryKeys.discoveredProjects,
    queryFn: ({ signal }) => api.discoverProjects(false, signal),
    staleTime: DISCOVER_STALE_MS,
  })
}

/** Scans the PC again (`?refresh=1`, bypassing the server cache) into the discover query. */
export function useRefreshDiscoveredProjects() {
  const qc = useQueryClient()
  return useCallback(
    () =>
      qc
        .fetchQuery({
          queryKey: queryKeys.discoveredProjects,
          queryFn: ({ signal }) => api.discoverProjects(true, signal),
          staleTime: 0,
        })
        .then(
          () => undefined,
          () => undefined, // reported by the query's error state
        ),
    [qc],
  )
}

export function useProject(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.project(id ?? ''),
    queryFn: () => api.getProject(id as string),
    enabled: Boolean(id),
  })
}

export function useProjectFile(id: string | null | undefined, path: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.projectFile(id ?? '', path ?? ''),
    queryFn: () => api.getProjectFile(id as string, path as string),
    enabled: Boolean(id && path),
    staleTime: Infinity,
  })
}

// ---- analyses & jobs -----------------------------------------------------------------------

export function useStartAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: StartAnalysisRequest) => api.startAnalysis(req),
    onSuccess: (_job, req) => {
      void qc.invalidateQueries({ queryKey: ['analyses', 'list'] })
      // The run re-snapshots path/demo projects: files viewed before must be read again.
      void qc.invalidateQueries({ queryKey: queryKeys.project(req.project_id) })
    },
  })
}

export function isJobFinished(job: JobState | undefined): boolean {
  return job?.status === 'done' || job?.status === 'error'
}

/** Polls a job every 400 ms until it is done or failed. */
export function useJob(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.job(id ?? ''),
    queryFn: ({ signal }) => api.getJob(id as string, signal),
    enabled: Boolean(id),
    refetchInterval: (query) => (isJobFinished(query.state.data) ? false : JOB_POLL_INTERVAL_MS),
    refetchIntervalInBackground: true,
    staleTime: 0,
  })
}

export function useAnalyses(params: ListAnalysesParams = {}) {
  return useQuery({ queryKey: queryKeys.analyses(params), queryFn: () => api.listAnalyses(params) })
}

export function useAnalysis(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.analysis(id ?? ''),
    queryFn: () => api.getAnalysis(id as string),
    enabled: Boolean(id),
    staleTime: Infinity, // a report never changes once written
  })
}

export function useComparison(id: string | null | undefined, baseId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.comparison(id ?? '', baseId ?? ''),
    queryFn: () => api.compareAnalyses(id as string, baseId as string),
    enabled: Boolean(id && baseId),
    staleTime: Infinity,
  })
}

export function useExplainCheck(analysisId: string) {
  return useMutation({
    mutationFn: ({ checkId, ...req }: ExplainRequest & { checkId: string }) =>
      api.explainCheck(analysisId, checkId, req),
  })
}

export function useAiPayload(analysisId: string, checkId: string | null, mode: AiPayloadMode, enabled = true) {
  return useQuery({
    queryKey: queryKeys.aiPayload(analysisId, checkId ?? '', mode),
    queryFn: () => api.getAiPayload(analysisId, checkId as string, mode),
    enabled: enabled && Boolean(checkId),
  })
}

// ---- demo ----------------------------------------------------------------------------------

export function useLoadDemo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (variant: DemoVariant) => api.loadDemo(variant),
    onSuccess: ({ subject, project }) => {
      qc.setQueryData(queryKeys.subject(subject.id), subject)
      qc.setQueryData(queryKeys.project(project.id), project)
    },
  })
}

/**
 * Starts a new analysis of the same (subject, project) pair. Path and demo projects are
 * re-copied by the backend at every analysis, so local edits are picked up without re-importing
 * (and the history numbering of the pair is kept). Zip/upload projects reuse their snapshot.
 */
export function useReanalyze() {
  return useStartAnalysis()
}
