import { CircleCheck, CircleDashed, LoaderCircle, Play } from 'lucide-react'
import { Button, Kbd } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { ImportState } from './import-card'
import { analyzeBlocker } from './logic'

export interface AnalyzeBarProps {
  subjectState: ImportState
  projectState: ImportState
  subjectLabel?: string | null
  projectLabel?: string | null
  starting: boolean
  error?: string | null
  /** Shown when everything is imported but no sandbox can run the code (the job would fail). */
  sandboxWarning?: string | null
  onAnalyze: () => void
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)

export function AnalyzeBar({
  subjectState,
  projectState,
  subjectLabel,
  projectLabel,
  starting,
  error,
  sandboxWarning,
  onAnalyze,
}: AnalyzeBarProps) {
  const blocker = analyzeBlocker(subjectState, projectState)
  const ready = blocker === null
  const warn = ready && !error && Boolean(sandboxWarning)
  return (
    <div className="sticky bottom-3 z-30 sm:bottom-5">
      <div
        className={cn(
          'flex flex-col gap-3 rounded-2xl border bg-surface/85 p-3 shadow-pop backdrop-blur-xl sm:flex-row sm:items-center sm:gap-4 sm:p-3.5 sm:pl-5',
          ready ? 'border-accent/35' : 'border-border-strong',
        )}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <ReadyItem label="Subject" state={subjectState} detail={subjectLabel} />
            <ReadyItem label="Project" state={projectState} detail={projectLabel} />
          </div>
          <p
            id="analyze-status"
            aria-live="polite"
            className={cn(
              'text-xs',
              error ? 'text-fail' : warn ? 'text-warning' : 'text-fg-subtle',
              // The default "all good" line is redundant with the check marks on small screens.
              ready && !error && !warn && 'max-sm:sr-only',
            )}
          >
            {error ??
              blocker ??
              (warn ? sandboxWarning : 'Everything is ready. The analysis runs locally in the sandbox.')}
          </p>
        </div>
        <Button
          variant="primary"
          size="lg"
          onClick={onAnalyze}
          disabled={!ready}
          loading={starting}
          aria-describedby="analyze-status"
          aria-keyshortcuts={isMac ? 'Meta+Enter' : 'Control+Enter'}
          className="w-full sm:w-auto"
        >
          {!starting && <Play aria-hidden className="fill-current" />}
          Analyze project
          <span className="ml-1 hidden items-center gap-0.5 sm:inline-flex" aria-hidden>
            <Kbd className="border-white/25 bg-white/10 text-white/85 shadow-none">{isMac ? '⌘' : 'Ctrl'}</Kbd>
            <Kbd className="border-white/25 bg-white/10 text-white/85 shadow-none">↵</Kbd>
          </span>
        </Button>
      </div>
    </div>
  )
}

function ReadyItem({ label, state, detail }: { label: string; state: ImportState; detail?: string | null }) {
  const Icon = state === 'ready' ? CircleCheck : state === 'uploading' || state === 'loading' ? LoaderCircle : CircleDashed
  return (
    <span className="inline-flex min-w-0 max-w-full items-center gap-1.5">
      <Icon
        className={cn(
          'size-3.5 shrink-0',
          state === 'ready' ? 'text-pass' : state === 'error' ? 'text-fail' : 'text-fg-subtle',
          (state === 'uploading' || state === 'loading') && 'animate-spin',
        )}
        aria-hidden
      />
      <span className="font-medium text-fg">{label}</span>
      <span className={cn('truncate text-fg-muted', state === 'ready' && detail && 'max-sm:sr-only')}>
        {state === 'ready' && detail ? detail : state === 'ready' ? 'ready' : state === 'error' ? 'error' : state === 'empty' ? 'missing' : '…'}
      </span>
    </span>
  )
}
