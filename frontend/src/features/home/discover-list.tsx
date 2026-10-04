import { ChevronRight, Clock, FolderGit2, FolderSearch, GitBranch, GraduationCap, HardDrive, Monitor, RefreshCw, Terminal } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Skeleton, Tooltip } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/cn'
import { formatRelativeTime } from '@/lib/format'
import { useDiscoverProjects, useRefreshDiscoveredProjects } from '@/lib/queries'
import type { DiscoveredProject } from '@/lib/types'

/** Rows shown before "Show all". */
const DISCOVER_VISIBLE = 6

export interface DiscoverListProps {
  onPick: (project: DiscoveredProject) => void
  onUseLocalFolder: () => void
}

/** "My projects" tab: the git repositories found on this PC, one click to import. */
export function DiscoverList({ onPick, onUseLocalFolder }: DiscoverListProps) {
  const query = useDiscoverProjects()
  const refresh = useRefreshDiscoveredProjects()
  const [showAll, setShowAll] = useState(false)

  const projects = query.data?.projects ?? []
  const refreshing = query.isFetching && !query.isPending
  const visible = showAll ? projects : projects.slice(0, DISCOVER_VISIBLE)
  const hidden = projects.length - DISCOVER_VISIBLE

  if (query.isPending) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <p className="flex items-center gap-2 text-xs text-fg-muted" role="status">
          <FolderSearch className="size-3.5 animate-pulse text-accent-fg" aria-hidden />
          Looking for your projects on this PC…
        </p>
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-border p-3">
            <Skeleton className="size-9 shrink-0 rounded-lg" />
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Skeleton className="h-4 w-2/5" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (query.isError && !query.data) {
    return (
      <div className="flex flex-col items-start gap-2.5 rounded-xl border border-fail/25 bg-fail/[0.05] p-3.5" role="alert">
        <p className="text-sm font-medium text-fg">Could not look for your projects.</p>
        <p className="text-xs break-words text-fg-muted">{errorMessage(query.error)}</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => void refresh()}>
            <RefreshCw aria-hidden />
            Try again
          </Button>
          <Button size="sm" variant="ghost" onClick={onUseLocalFolder}>
            <HardDrive aria-hidden />
            Type the folder address instead
          </Button>
        </div>
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2.5 rounded-xl border border-dashed border-border-strong px-4 py-5 text-center">
        <FolderSearch className="size-6 text-fg-subtle" aria-hidden />
        <p className="text-sm font-medium text-fg">No project found automatically.</p>
        <p className="max-w-sm text-xs text-fg-muted">
          Use the Local folder tab and paste the folder address. In Ubuntu, type{' '}
          <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.7rem] text-fg">wslpath -w .</code> in your
          project folder to get it.
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button size="sm" variant="secondary" onClick={onUseLocalFolder}>
            <HardDrive aria-hidden />
            Use the Local folder tab
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void refresh()} disabled={refreshing}>
            <RefreshCw aria-hidden className={cn(refreshing && 'animate-spin')} />
            Search again
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-fg-muted">
          {projects.length === 1 ? 'Found 1 project.' : `Found ${projects.length} projects.`} Click yours to use it.
        </p>
        <Tooltip content={refreshing ? 'Searching…' : 'Search again'}>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Search again for projects"
            onClick={() => void refresh()}
            disabled={refreshing}
          >
            <RefreshCw aria-hidden className={cn(refreshing && 'animate-spin')} />
          </Button>
        </Tooltip>
      </div>

      <ul
        aria-label="Projects found on this PC"
        className={cn('flex flex-col gap-1.5', showAll && projects.length > DISCOVER_VISIBLE && 'max-h-[30rem] overflow-y-auto pr-1')}
      >
        {visible.map((project) => (
          <li key={project.path}>
            <ProjectRow project={project} onPick={onPick} />
          </li>
        ))}
      </ul>

      {hidden > 0 && (
        <Button size="sm" variant="ghost" className="self-start" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
          {showAll ? 'Show fewer' : `Show all (${hidden} more)`}
        </Button>
      )}
    </div>
  )
}

function locationLabel(project: DiscoveredProject): string {
  if (project.location === 'wsl') return project.distro || 'WSL'
  if (project.location === 'windows') return 'Windows'
  return 'This PC'
}

function ProjectRow({ project, onPick }: { project: DiscoveredProject; onPick: (p: DiscoveredProject) => void }) {
  const LocationIcon = project.location === 'wsl' ? Terminal : Monitor
  const when = project.last_activity ? formatRelativeTime(project.last_activity) : ''
  return (
    <button
      type="button"
      onClick={() => onPick(project)}
      title={project.last_message ? `Last change: ${project.last_message}` : undefined}
      className={cn(
        'group flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-colors duration-150',
        'hover:border-accent/50 hover:bg-accent/[0.06] active:translate-y-px',
        project.is_school ? 'border-accent/25 bg-accent/[0.03]' : 'border-border bg-bg-subtle/60',
      )}
    >
      <span
        className={cn(
          'flex size-9 shrink-0 items-center justify-center rounded-lg',
          project.is_school ? 'bg-accent/15 text-accent-fg' : 'bg-surface-2 text-fg-muted',
        )}
      >
        <FolderGit2 className="size-5" aria-hidden />
      </span>

      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="min-w-0 truncate text-sm font-semibold text-fg" title={project.name}>
            {project.name}
          </span>
          <Badge tone={project.location === 'wsl' ? 'info' : 'neutral'}>
            <LocationIcon aria-hidden />
            {locationLabel(project)}
          </Badge>
          {project.is_school && (
            <Badge tone="accent">
              <GraduationCap aria-hidden />
              School
            </Badge>
          )}
        </span>
        {(project.branch || when) && (
          <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-fg-muted">
            {project.branch && (
              <span className="inline-flex min-w-0 items-center gap-1">
                <GitBranch className="size-3.5 shrink-0" aria-hidden />
                <span className="truncate">{project.branch}</span>
              </span>
            )}
            {when && (
              <span className="inline-flex items-center gap-1">
                <Clock className="size-3.5 shrink-0" aria-hidden />
                last change {when}
              </span>
            )}
          </span>
        )}
        <span className="truncate font-mono text-2xs text-fg-subtle" title={project.display_path}>
          {project.display_path}
        </span>
      </span>

      <ChevronRight
        className="size-4 shrink-0 text-fg-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-accent-fg"
        aria-hidden
      />
    </button>
  )
}
