import type { Health } from '@/lib/types'

export type SandboxTone = 'pass' | 'warning' | 'fail' | 'neutral'

export interface SandboxStatus {
  kind: 'docker' | 'local' | 'none' | 'offline' | 'loading'
  tone: SandboxTone
  /** Short pill label. */
  label: string
  /** Longer explanation for tooltips and banners. */
  description: string
}

const LOCAL_DESCRIPTION =
  'Developer mode: student code runs on this machine in a restricted child process (minimal environment, ' +
  'timeouts, process limits). Isolation is weaker than Docker: only analyze code you trust.'

/** Maps GET /api/health to what the shell pill and the home banner display. */
export function describeSandbox(health: Health | undefined, opts: { loading?: boolean; error?: boolean } = {}): SandboxStatus {
  if (!health) {
    if (opts.error) {
      return {
        kind: 'offline',
        tone: 'fail',
        label: 'Server offline',
        description: 'Cannot reach the PréMoulinette server. Start it with "python -m premoulinette".',
      }
    }
    return { kind: 'loading', tone: 'neutral', label: 'Checking sandbox…', description: 'Checking the sandbox status…' }
  }
  const note = health.sandbox_note?.trim()
  switch (health.sandbox_mode_effective) {
    case 'docker':
      return {
        kind: 'docker',
        tone: 'pass',
        label: 'Safe mode · Docker',
        description:
          'Safe mode: student code runs in a throw-away Docker container (no network, read-only project, ' +
          `CPU / memory / process limits)${health.docker.version ? ` · Docker ${health.docker.version}` : ''}.`,
      }
    case 'local':
      return {
        kind: 'local',
        tone: 'warning',
        label: 'Developer mode',
        description: note ? `${LOCAL_DESCRIPTION} ${note}` : LOCAL_DESCRIPTION,
      }
    default:
      return {
        kind: 'none',
        tone: 'fail',
        label: 'Sandbox not configured',
        description: note || 'No sandbox can run student code yet. Open Settings to choose Docker or Developer mode.',
      }
  }
}
