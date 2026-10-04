/**
 * Client-side stand-in for the analysis job of the backend (engine/jobs.py + engine/pipeline.py):
 * the same seven stages, at the same progress points, played over a few seconds.
 */
import type { JobStage, JobState } from '../types'

/** [key, label, progress at which the stage starts] — mirrors STAGES / _STAGE_START of the pipeline. */
export const DEMO_STAGES: ReadonlyArray<readonly [key: string, label: string, start: number]> = [
  ['subject', 'Parsing subject…', 0],
  ['repository', 'Inspecting repository…', 0.05],
  ['compile', 'Compiling Python files…', 0.25],
  ['explicit', 'Running explicit tests…', 0.4],
  ['derived', 'Running derived tests…', 0.75],
  ['constraints', 'Checking constraints…', 0.85],
  ['report', 'Building report…', 0.92],
]

export const DEMO_JOB_DURATION_MS = 4000

export interface SimulatedJob {
  id: string
  /** Analysis the job "produces". */
  target: string
  /** Epoch ms. */
  startedAt: number
}

/** The JobState of `job` at time `now` (epoch ms). Pure and deterministic. */
export function simulateJob(job: SimulatedJob, now: number, durationMs = DEMO_JOB_DURATION_MS): JobState {
  const elapsed = Math.max(0, now - job.startedAt)
  const created_at = new Date(job.startedAt).toISOString()
  if (elapsed >= durationMs) {
    return {
      id: job.id,
      kind: 'analysis',
      status: 'done',
      stage: DEMO_STAGES[DEMO_STAGES.length - 1]?.[0] ?? null,
      stages: DEMO_STAGES.map(([key, label]) => ({ key, label, status: 'done' })),
      progress: 1,
      result_id: job.target,
      error: null,
      created_at,
      finished_at: new Date(job.startedAt + durationMs).toISOString(),
    }
  }
  const progress = durationMs > 0 ? elapsed / durationMs : 1
  let current = 0
  DEMO_STAGES.forEach(([, , start], i) => {
    if (start <= progress) current = i
  })
  const stages: JobStage[] = DEMO_STAGES.map(([key, label], i) => ({
    key,
    label,
    status: i < current ? 'done' : i === current ? 'running' : 'pending',
  }))
  return {
    id: job.id,
    kind: 'analysis',
    status: 'running',
    stage: DEMO_STAGES[current]?.[0] ?? null,
    stages,
    progress: Math.min(progress, 0.99),
    result_id: null,
    error: null,
    created_at,
    finished_at: null,
  }
}
