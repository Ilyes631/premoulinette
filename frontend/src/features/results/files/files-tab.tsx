import { ChevronRight, Folder, FolderOpen, FolderTree } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge, Card, EmptyState, Tooltip } from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatPercent } from '@/lib/format'
import type { TreeEntry, TreeEntryStatus } from '@/lib/types'
import { TREE_STATUS_META } from '../shared/meta'
import { useResults } from '../shared/results-context'
import { buildTreeRows, fileScoreFor, type TreeRow } from '../shared/selectors'

const GIT_BADGE: Partial<Record<NonNullable<TreeEntry['git']>, { label: string; tone: 'warning' | 'info' | 'neutral' }>> = {
  untracked: { label: 'untracked', tone: 'warning' },
  modified: { label: 'modified', tone: 'info' },
  ignored: { label: 'ignored', tone: 'neutral' },
}

const SUMMARY_ORDER: TreeEntryStatus[] = ['missing', 'misplaced', 'parasite', 'extra', 'expected']

export function FilesTab() {
  const { report, openFile } = useResults()
  const rows = useMemo(() => buildTreeRows(report.tree), [report.tree])
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set())

  const summary = useMemo(() => {
    const counts = new Map<TreeEntryStatus, number>()
    for (const e of report.tree) if (e.kind === 'file') counts.set(e.status, (counts.get(e.status) ?? 0) + 1)
    return counts
  }, [report.tree])
  const fileCount = report.tree.filter((e) => e.kind === 'file' && e.status !== 'missing').length

  if (rows.length === 0) {
    return <EmptyState icon={FolderTree} title="No files" description="The project snapshot is empty." />
  }

  const visible = rows.filter((r) => !r.ancestors.some((a) => collapsed.has(a)))
  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
        <span>
          <span className="font-medium text-fg tabular">{fileCount}</span> files
        </span>
        {SUMMARY_ORDER.filter((s) => summary.get(s)).map((s) => {
          const meta = TREE_STATUS_META[s]
          return (
            <span key={s} className="inline-flex items-center gap-1">
              <span className="text-fg-subtle">·</span>
              <meta.icon className={cn('size-3.5', meta.className)} aria-hidden />
              <span className="tabular">{summary.get(s)}</span> {meta.label.toLowerCase()}
            </span>
          )
        })}
        {report.project.detected_root && (
          <span className="ml-auto font-mono text-2xs text-fg-subtle">root: {report.project.detected_root}/</span>
        )}
      </div>
      <Card className="overflow-hidden py-1.5">
        <ul aria-label="Project files">
          {visible.map((row) => (
            <TreeRowItem
              key={row.entry.path}
              row={row}
              expanded={!collapsed.has(row.entry.path)}
              onToggle={() => toggle(row.entry.path)}
              onOpen={() => openFile({ file: row.entry.path, line: null })}
              scorePct={fileScoreFor(row.entry.path, report.score.files, report.project.detected_root)?.score ?? null}
            />
          ))}
        </ul>
      </Card>
      <p className="text-xs text-fg-subtle">Click a file to view it. Files are shown read-only from the analyzed snapshot.</p>
    </div>
  )
}

interface TreeRowItemProps {
  row: TreeRow
  expanded: boolean
  onToggle: () => void
  onOpen: () => void
  scorePct: number | null
}

function TreeRowItem({ row, expanded, onToggle, onOpen, scorePct }: TreeRowItemProps) {
  const { entry, depth, name } = row
  const isDir = entry.kind === 'directory'
  const meta = TREE_STATUS_META[entry.status]
  const missing = entry.status === 'missing'
  const Icon = isDir ? (expanded ? FolderOpen : Folder) : meta.icon
  const git = entry.git ? GIT_BADGE[entry.git] : undefined
  const iconClass = isDir
    ? entry.status === 'missing'
      ? 'text-fail'
      : 'text-fg-subtle'
    : entry.bonus && missing
      ? 'text-bonus'
      : meta.className
  return (
    <li data-nav-row>
      <button
        type="button"
        onClick={isDir ? onToggle : onOpen}
        aria-expanded={isDir ? expanded : undefined}
        disabled={!isDir && missing}
        className={cn(
          'flex w-full items-center gap-2 py-1.5 pr-3 text-left transition-colors hover:bg-surface-2 disabled:cursor-default disabled:hover:bg-transparent sm:pr-4',
        )}
        style={{ paddingLeft: `${0.75 + depth * 1.125}rem` }}
      >
        <ChevronRight
          className={cn('size-3.5 shrink-0 text-fg-subtle transition-transform', !isDir && 'invisible', expanded && 'rotate-90')}
          aria-hidden
        />
        <Tooltip content={isDir ? undefined : `${meta.label}: ${meta.hint}`}>
          <Icon className={cn('size-4 shrink-0', iconClass)} aria-hidden />
        </Tooltip>
        {!isDir && <span className="sr-only">{meta.label}: </span>}
        <span
          className={cn(
            'min-w-0 truncate font-mono text-[0.8125rem]',
            missing ? 'text-fg-subtle line-through decoration-fail/50' : 'text-fg',
          )}
        >
          {name}
          {isDir && '/'}
        </span>
        {entry.note && <span className="hidden min-w-0 truncate text-2xs text-fg-subtle md:inline">{entry.note}</span>}
        <span className="ml-auto flex shrink-0 items-center gap-1.5">
          {entry.bonus && (
            <Badge tone="bonus" variant="outline">
              bonus
            </Badge>
          )}
          {!isDir && entry.status !== 'ok' && entry.status !== 'expected' && (
            <Badge tone={missing || entry.status === 'misplaced' ? (entry.bonus ? 'bonus' : 'fail') : entry.status === 'parasite' ? 'warning' : 'info'}>
              {meta.label}
            </Badge>
          )}
          {git && <Badge tone={git.tone} variant="outline">{git.label}</Badge>}
          {scorePct !== null && !isDir && (
            <span
              className={cn(
                'w-11 text-right text-xs font-medium tabular',
                scorePct >= 100 ? 'text-pass' : scorePct >= 70 ? 'text-warning' : 'text-fail',
              )}
            >
              {formatPercent(scorePct)}
            </span>
          )}
        </span>
      </button>
    </li>
  )
}
