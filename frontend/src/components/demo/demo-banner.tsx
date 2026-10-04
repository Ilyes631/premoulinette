import { BookOpen } from 'lucide-react'
import { INSTALL_URL, REPO_URL } from '@/lib/demo/config'
import { GithubMark } from './github-mark'

const LINK =
  'inline-flex items-center gap-1 rounded-sm font-medium text-accent-fg underline-offset-4 transition-colors hover:underline'

/** Slim strip above the top bar of the online demo: what this is, and where to get the real tool. */
export function DemoBanner() {
  return (
    <div role="region" aria-label="Online demo" className="border-b border-accent/20 bg-accent/[0.07] text-xs">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-center gap-x-3 gap-y-1 px-4 py-1.5 text-center sm:px-6">
        <p className="flex items-center gap-1.5 text-fg">
          <span className="relative flex size-1.5 shrink-0" aria-hidden>
            <span className="absolute inset-0 animate-ping rounded-full bg-accent opacity-50 motion-reduce:hidden" />
            <span className="relative size-1.5 rounded-full bg-accent" />
          </span>
          <span className="font-medium">Live demo · read-only</span>
          <span className="hidden text-fg-muted sm:inline">— run it locally to analyze your own TP</span>
        </p>
        <span aria-hidden className="hidden h-3 w-px bg-border-strong sm:block" />
        <span className="flex items-center gap-3">
          <a href={REPO_URL} target="_blank" rel="noreferrer" className={LINK}>
            <GithubMark className="size-3.5" />
            GitHub
          </a>
          <a href={INSTALL_URL} target="_blank" rel="noreferrer" className={LINK}>
            <BookOpen className="size-3.5" aria-hidden />
            How to install
          </a>
        </span>
      </div>
    </div>
  )
}
