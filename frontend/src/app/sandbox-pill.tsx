import { Link } from 'react-router-dom'
import { Tooltip } from '@/components/ui'
import { cn } from '@/lib/cn'
import { useHealth } from '@/lib/queries'
import { describeSandbox, type SandboxTone } from './sandbox-status'

const PILL: Record<SandboxTone, string> = {
  pass: 'border-pass/25 bg-pass/10 text-pass hover:bg-pass/15',
  warning: 'border-warning/30 bg-warning/10 text-warning hover:bg-warning/15',
  fail: 'border-fail/30 bg-fail/10 text-fail hover:bg-fail/15',
  neutral: 'border-border-strong bg-surface-2 text-fg-muted hover:text-fg',
  accent: 'border-accent/30 bg-accent/10 text-accent-fg hover:bg-accent/15',
}

const DOT: Record<SandboxTone, string> = {
  pass: 'bg-pass',
  warning: 'bg-warning',
  fail: 'bg-fail',
  neutral: 'bg-fg-subtle',
  accent: 'bg-accent',
}

/** Top-bar pill showing where student code will run. Always links to the sandbox settings. */
export function SandboxPill({ className }: { className?: string }) {
  const health = useHealth()
  const status = describeSandbox(health.data, { loading: health.isPending, error: health.isError })
  const pulsing = status.kind === 'loading'
  return (
    <Tooltip content={<span className="block max-w-64">{status.description}</span>} side="bottom" align="end">
      <Link
        to="/settings"
        aria-label={`Sandbox: ${status.label}. Open settings`}
        data-sandbox={status.kind}
        className={cn(
          'inline-flex h-7 items-center gap-2 rounded-full border px-2 text-xs font-medium transition-colors md:px-2.5',
          PILL[status.tone],
          className,
        )}
      >
        <span className="relative flex size-2 shrink-0" aria-hidden>
          {(status.tone === 'pass' || pulsing) && (
            <span className={cn('absolute inset-0 animate-ping rounded-full opacity-40 motion-reduce:hidden', DOT[status.tone])} />
          )}
          <span className={cn('relative size-2 rounded-full', DOT[status.tone])} />
        </span>
        <span className="hidden whitespace-nowrap md:inline">{status.label}</span>
      </Link>
    </Tooltip>
  )
}
