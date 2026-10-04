import { useQueryClient } from '@tanstack/react-query'
import { Box, CircleCheck, CircleX, Download, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { Badge, Button, Input, ProgressBar, Skeleton } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { toastDemoReadOnly } from '@/lib/demo/notify'
import { cn } from '@/lib/cn'
import { queryKeys, useHealth, useJob, usePrepareSandbox } from '@/lib/queries'
import { toast } from '@/lib/toast'
import type { SandboxPreference } from '@/lib/types'
import { FieldError, RadioCards, SettingsSection } from './parts'
import type { SettingsDraft } from './settings-form'

const EFFECTIVE_LABEL: Record<string, string> = {
  docker: 'Docker safe mode',
  local: 'Developer mode (local)',
  none: 'No sandbox available',
}

export interface SandboxSectionProps {
  draft: SettingsDraft
  onChange: (patch: Partial<SettingsDraft>) => void
  errors: Partial<Record<keyof SettingsDraft, string>>
}

export function SandboxSection({ draft, onChange, errors }: SandboxSectionProps) {
  const health = useHealth()
  const docker = health.data?.docker
  const dockerAvailable = docker?.available === true
  const ackId = useId()
  const imageId = useId()
  const needsAck = draft.sandbox_mode === 'local' || (draft.sandbox_mode === 'auto' && health.data !== undefined && !dockerAvailable)

  return (
    <SettingsSection
      id="sandbox"
      icon={ShieldCheck}
      title="Sandbox"
      description="Where student code runs. Static checks never execute code; only tests run in the sandbox."
    >
      <RadioCards<SandboxPreference>
        name="sandbox_mode"
        legend="Execution mode"
        value={draft.sandbox_mode}
        onChange={(v) => onChange({ sandbox_mode: v })}
        options={[
          {
            value: 'auto',
            title: 'Auto',
            description: 'Docker when available; otherwise Developer mode, only if you acknowledged it below.',
            badge: <Badge tone="accent">Recommended</Badge>,
          },
          {
            value: 'docker',
            title: 'Docker safe mode',
            description: 'Throw-away container: no network, read-only project, memory / CPU / process limits.',
            badge: !health.isPending && !dockerAvailable ? <Badge tone="warning">Unavailable</Badge> : undefined,
          },
          {
            value: 'local',
            title: 'Developer mode',
            description: 'Runs on this machine in a child process with best-effort limits. Trusted code only.',
            badge: <Badge tone="fail">Weaker isolation</Badge>,
          },
        ]}
      />

      {needsAck && (
        <div className="rounded-lg border border-fail/30 bg-fail/8 px-4 py-3.5">
          <p className="flex items-center gap-2 text-sm font-semibold text-fail">
            <ShieldAlert className="size-4 shrink-0" aria-hidden /> Developer mode runs code on your machine
          </p>
          <p className="mt-1.5 text-sm text-pretty text-fg">
            Student code will run on your machine with limited isolation: no container, best-effort limits (timeouts,
            memory and process caps, network and subprocess calls blocked by an audit hook). A malicious program could
            still read or damage your files. Only analyze code you trust — ideally your own.
          </p>
          <label htmlFor={ackId} className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-fg">
            <input
              id={ackId}
              type="checkbox"
              checked={draft.local_mode_acknowledged}
              onChange={(e) => onChange({ local_mode_acknowledged: e.target.checked })}
              className="mt-0.5 size-4 accent-fail"
            />
            <span>I understand the risks and allow Developer mode on this machine.</span>
          </label>
          <FieldError message={errors.local_mode_acknowledged} />
        </div>
      )}

      <DockerStatusPanel />

      <div className="max-w-md">
        <label htmlFor={imageId} className="mb-1.5 block text-xs font-medium text-fg-muted">
          Docker image
        </label>
        <Input
          id={imageId}
          value={draft.docker_image}
          spellCheck={false}
          invalid={Boolean(errors.docker_image)}
          onChange={(e) => onChange({ docker_image: e.target.value })}
          className="font-mono text-[0.8125rem]"
        />
        <FieldError message={errors.docker_image} />
        <p className="mt-1.5 text-xs text-fg-subtle">Python image used by the safe mode (official python:*-slim images recommended).</p>
      </div>

      {health.data && (
        <p className="text-xs text-fg-muted">
          Currently used:{' '}
          <span className={cn('font-medium', health.data.sandbox_mode_effective === 'none' ? 'text-fail' : 'text-fg')}>
            {EFFECTIVE_LABEL[health.data.sandbox_mode_effective ?? 'none'] ?? health.data.sandbox_mode_effective}
          </span>
          {health.data.sandbox_note && <span className="text-fg-subtle"> — {health.data.sandbox_note}</span>}
        </p>
      )}
    </SettingsSection>
  )
}

function DockerStatusPanel() {
  const health = useHealth()
  const qc = useQueryClient()
  const prepare = usePrepareSandbox()
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId)
  const handled = useRef<string | null>(null)

  useEffect(() => {
    const state = job.data
    if (!state || handled.current === state.id) return
    if (state.status === 'done') {
      handled.current = state.id
      toast({ title: 'Sandbox image ready', description: 'Docker safe mode can run analyses.', tone: 'success' })
      void qc.invalidateQueries({ queryKey: queryKeys.health })
    } else if (state.status === 'error') {
      handled.current = state.id
      toast({ title: 'The image could not be prepared', description: state.error ?? undefined, tone: 'error' })
    }
  }, [job.data, qc])

  if (health.isPending) return <Skeleton className="h-20" />
  if (health.isError) {
    return (
      <div className="rounded-lg border border-border bg-surface-2/40 px-4 py-3 text-sm text-fg-muted">
        Docker status unknown: {errorMessage(health.error)}
      </div>
    )
  }
  const docker = health.data.docker
  const running = job.data !== undefined && (job.data.status === 'queued' || job.data.status === 'running')

  const start = async () => {
    try {
      const { job_id } = await prepare.mutateAsync()
      setJobId(job_id)
    } catch (error) {
      if (toastDemoReadOnly(error)) return
      toast({ title: 'The image could not be prepared', description: errorMessage(error), tone: 'error' })
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface-2/40 px-4 py-3.5" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="flex items-center gap-2 text-sm font-medium text-fg">
          <Box className="size-4 text-fg-muted" aria-hidden /> Docker
        </span>
        {docker.available ? (
          <Badge tone="pass">
            <CircleCheck aria-hidden /> Available{docker.version ? ` · ${docker.version}` : ''}
          </Badge>
        ) : (
          <Badge tone="fail">
            <CircleX aria-hidden /> Not available
          </Badge>
        )}
        {docker.available && (
          <span className="flex items-center gap-1.5 text-xs text-fg-muted">
            <code className="font-mono text-fg">{docker.image}</code>
            {docker.image_ready ? <Badge tone="pass">Image ready</Badge> : <Badge tone="warning">Image not downloaded</Badge>}
          </span>
        )}
        {docker.available && (
          <Button
            size="sm"
            variant={docker.image_ready ? 'ghost' : 'primary'}
            className="ml-auto"
            onClick={start}
            loading={prepare.isPending || running}
          >
            <Download aria-hidden /> {docker.image_ready ? 'Update sandbox image' : 'Prepare sandbox image'}
          </Button>
        )}
      </div>
      {!docker.available && (
        <p className="mt-2 text-xs text-fg-muted">
          {docker.error ? `${docker.error} ` : ''}Install and start Docker Desktop to use the safe mode.
        </p>
      )}
      {running && job.data && (
        <div className="mt-3 space-y-1">
          <ProgressBar
            label="Sandbox image download"
            value={job.data.progress > 0.05 && job.data.progress < 1 ? job.data.progress * 100 : undefined}
          />
          <p className="text-xs text-fg-muted">{job.data.stages.find((s) => s.status === 'running')?.label ?? 'Preparing…'}</p>
        </div>
      )}
      {job.data?.status === 'error' && <p className="mt-2 text-xs text-fail">{job.data.error}</p>}
    </div>
  )
}
