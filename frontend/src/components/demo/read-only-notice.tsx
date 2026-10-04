import { BookOpen, Lock } from 'lucide-react'
import { cn } from '@/lib/cn'
import { DEMO_READ_ONLY_MESSAGE, INSTALL_URL, REPO_URL } from '@/lib/demo/config'
import { GithubMark } from './github-mark'

const LINK = 'inline-flex items-center gap-1 rounded-sm font-medium text-accent-fg underline-offset-4 hover:underline'

/** Inline explanation shown where the online demo refuses an action (upload, save, AI...). */
export function DemoReadOnlyNotice({ action, className }: { action?: string; className?: string }) {
  return (
    <div
      role="status"
      className={cn('flex items-start gap-2.5 rounded-lg border border-accent/25 bg-accent/[0.06] px-3 py-2.5 text-sm', className)}
    >
      <Lock className="mt-0.5 size-4 shrink-0 text-accent-fg" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-fg">
          {action ? `${action} is not available in the online demo` : 'Read-only online demo'}
        </p>
        <p className="mt-0.5 text-pretty text-fg-muted">{DEMO_READ_ONLY_MESSAGE}</p>
        <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <a href={REPO_URL} target="_blank" rel="noreferrer" className={LINK}>
            <GithubMark className="size-3.5" />
            Get PréMoulinette on GitHub
          </a>
          <a href={INSTALL_URL} target="_blank" rel="noreferrer" className={LINK}>
            <BookOpen className="size-3.5" aria-hidden />
            How to install
          </a>
        </p>
      </div>
    </div>
  )
}
