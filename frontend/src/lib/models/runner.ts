/** Mirror of backend/premoulinette/runner/models.py (sandbox execution protocol). */

export interface FunctionJob {
  kind: 'function'
  id: string
  module_path: string
  function: string
  args: string[]
  kwargs: Record<string, string>
  timeout_s: number
}

export interface ScriptJob {
  kind: 'script'
  id: string
  script_path: string
  argv: string[]
  stdin: string
  timeout_s: number
}

export interface ImportJob {
  kind: 'import'
  id: string
  module_path: string
  timeout_s: number
}

export type Job = FunctionJob | ScriptJob | ImportJob

export interface RunPlan {
  jobs: Job[]
  max_parallel: number
  max_output_bytes: number
  cwd_mode: 'script_dir' | 'project_root'
}

export interface RawEvent {
  kind: 'output' | 'input' | 'stderr'
  text: string
  file: string | null
  line: number | null
}

export interface RawException {
  type: string
  message: string
  traceback: string
  file: string | null
  line: number | null
}

export type JobStatus =
  | 'ok'
  | 'exception'
  | 'timeout'
  | 'import_error'
  | 'syntax_error'
  | 'crash'
  | 'output_limit'
  | 'harness_error'

export interface JobResult {
  id: string
  kind: 'function' | 'script' | 'import'
  status: JobStatus
  duration_ms: number
  return_repr: string | null
  return_type: string | null
  return_literal: boolean
  import_stdout: string
  stdout: string
  stderr: string
  exit_code: number | null
  events: RawEvent[]
  exception: RawException | null
  truncated: boolean
  blocked_syscalls: string[]
  harness_error: string | null
}

export interface RunResults {
  results: JobResult[]
  python_version: string | null
  sandbox_mode: 'docker' | 'local'
  total_ms: number
  errors: string[]
}
