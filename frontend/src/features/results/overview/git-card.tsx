import { GitBranch, GitCommitHorizontal, TriangleAlert } from 'lucide-react'
import { Badge } from '@/components/ui'
import { formatDateTime, formatRelativeTime } from '@/lib/format'
import type { GitInfo } from '@/lib/types'
import { SectionCard } from '../shared/section-card'

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`
}

export function GitCard({ git }: { git: GitInfo | null }) {
  return (
    <SectionCard icon={GitBranch} title="Git" description="What will actually be submitted.">
      {!git ? (
        <p className="text-sm text-fg-muted">Git information is not available for this analysis.</p>
      ) : !git.is_repo ? (
        <div className="space-y-1.5">
          <p className="flex items-center gap-2 text-sm font-medium text-warning">
            <TriangleAlert className="size-4" aria-hidden /> Not a Git repository
          </p>
          <p className="text-xs text-fg-muted">
            Moulinettes grade what is pushed. Initialize the repository and commit your files.
          </p>
          {git.error && <p className="font-mono text-2xs text-fg-subtle">{git.error}</p>}
        </div>
      ) : (
        <div className="space-y-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge size="md" variant="outline" className="font-mono">
              <GitBranch aria-hidden />
              {git.branch ?? 'detached HEAD'}
            </Badge>
            {git.dirty ? (
              <Badge size="md" tone="warning">
                Uncommitted changes
              </Badge>
            ) : (
              <Badge size="md" tone="pass">
                Clean
              </Badge>
            )}
          </div>
          {(git.last_commit_message || git.head) && (
            <div className="flex items-start gap-2 rounded-md border border-border bg-surface-2/50 px-3 py-2">
              <GitCommitHorizontal className="mt-0.5 size-4 shrink-0 text-fg-subtle" aria-hidden />
              <div className="min-w-0">
                <p className="truncate text-sm text-fg">{git.last_commit_message ?? 'Last commit'}</p>
                <p className="text-2xs text-fg-subtle">
                  {git.head && <span className="font-mono">{git.head.slice(0, 7)}</span>}
                  {git.head && git.last_commit_date && ' · '}
                  {git.last_commit_date && (
                    <time dateTime={git.last_commit_date} title={formatDateTime(git.last_commit_date)}>
                      {formatRelativeTime(git.last_commit_date)}
                    </time>
                  )}
                </p>
              </div>
            </div>
          )}
          <ul className="space-y-1.5 text-xs">
            {git.untracked.length > 0 && (
              <li className="flex items-start gap-1.5 text-warning">
                <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
                <span>{plural(git.untracked.length, 'file is', 'files are')} not tracked by Git</span>
              </li>
            )}
            {git.ignored_required.length > 0 && (
              <li className="flex items-start gap-1.5 text-fail">
                <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
                <span>
                  {plural(git.ignored_required.length, 'required file is', 'required files are')} ignored by .gitignore
                </span>
              </li>
            )}
            {git.modified.length > 0 && (
              <li className="text-fg-muted">{plural(git.modified.length, 'modified file', 'modified files')} not committed</li>
            )}
            {git.staged.length > 0 && (
              <li className="text-fg-muted">{plural(git.staged.length, 'staged file', 'staged files')}</li>
            )}
            {git.untracked.length === 0 && git.ignored_required.length === 0 && !git.dirty && (
              <li className="text-fg-muted">Everything is committed.</li>
            )}
          </ul>
          {git.untracked.length > 0 && (
            <details className="group text-xs">
              <summary className="text-fg-muted hover:text-fg">Show untracked files</summary>
              <ul className="mt-1.5 max-h-32 space-y-0.5 overflow-auto font-mono text-2xs text-fg-subtle">
                {git.untracked.map((f) => (
                  <li key={f} className="truncate">
                    {f}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </SectionCard>
  )
}
