import { Box, CalendarClock, FolderGit2, RotateCw, ShieldAlert, ShieldCheck, Timer } from 'lucide-react'
import { Badge, Button, Kbd, Tooltip } from '@/components/ui'
import { formatDateTime, formatDuration, formatRelativeTime } from '@/lib/format'
import type { AnalysisReport, SandboxInfo } from '@/lib/types'
import { ExportMenu } from './export-menu'

export function SandboxChip({ sandbox }: { sandbox: SandboxInfo }) {
  const docker = sandbox.mode === 'docker'
  const details = [
    docker ? `Docker${sandbox.image ? ` · ${sandbox.image}` : ''}` : 'Local process with OS limits (weaker isolation)',
    sandbox.python_version ? `Python ${sandbox.python_version}` : null,
    sandbox.network ? 'Network allowed' : 'Network disabled',
    ...sandbox.warnings,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <Tooltip content={details}>
      <span tabIndex={0} className="inline-flex rounded-md">
        <Badge tone={docker ? 'pass' : 'warning'} variant="outline" size="md">
          {docker ? <ShieldCheck aria-hidden /> : <ShieldAlert aria-hidden />}
          {docker ? 'Safe mode · Docker' : 'Developer mode · Local'}
        </Badge>
      </span>
    </Tooltip>
  )
}

interface ResultsHeaderProps {
  report: AnalysisReport
  onReanalyze: () => void
  reanalyzing: boolean
}

export function ResultsHeader({ report, onReanalyze, reanalyzing }: ResultsHeaderProps) {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0 space-y-2">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted">
          <span className="font-medium text-fg-subtle tabular">Analysis #{report.number}</span>
          <span aria-hidden className="text-fg-subtle">
            /
          </span>
          <span className="inline-flex items-center gap-1">
            <CalendarClock className="size-3.5" aria-hidden />
            <time dateTime={report.created_at} title={formatDateTime(report.created_at)}>
              {formatRelativeTime(report.created_at)}
            </time>
          </span>
          <span className="inline-flex items-center gap-1">
            <Timer className="size-3.5" aria-hidden />
            <span className="tabular">{formatDuration(report.duration_ms)}</span>
          </span>
        </p>
        <h1 className="text-xl font-semibold tracking-tight text-pretty text-fg sm:text-2xl">{report.subject.title}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Badge size="md" variant="outline">
            <FolderGit2 aria-hidden />
            <span className="max-w-56 truncate">{report.project.name}</span>
          </Badge>
          {report.project.git?.branch && (
            <Badge size="md" variant="outline" className="font-mono">
              {report.project.git.branch}
            </Badge>
          )}
          <SandboxChip sandbox={report.sandbox} />
          <Badge size="md" variant="outline">
            <Box aria-hidden />
            {report.subject.language === 'python' ? 'Python' : report.subject.language}
          </Badge>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <ExportMenu analysisId={report.id} />
        <Tooltip content="Run a new analysis of the same project (picks up your latest edits)">
          <Button variant="primary" onClick={onReanalyze} loading={reanalyzing} aria-keyshortcuts="r">
            {!reanalyzing && <RotateCw aria-hidden />}
            Re-analyze
            <Kbd className="ml-0.5 hidden border-white/25 bg-white/10 text-white/80 shadow-none sm:inline-flex">R</Kbd>
          </Button>
        </Tooltip>
      </div>
    </header>
  )
}
