import { ArrowRight, ServerOff, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { describeSandbox } from '@/app/sandbox-status'
import { useHealth } from '@/lib/queries'

/**
 * Shown above the import cards when an analysis could not run student code: no sandbox configured
 * (Docker unavailable and Developer mode not acknowledged) or the server is unreachable.
 */
export function SandboxBanner() {
  const health = useHealth()
  const status = describeSandbox(health.data, { loading: health.isPending, error: health.isError })
  if (status.kind !== 'none' && status.kind !== 'offline') return null

  const offline = status.kind === 'offline'
  const Icon = offline ? ServerOff : ShieldAlert
  return (
    <div
      role="alert"
      className={
        offline
          ? 'flex flex-col gap-3 rounded-xl border border-fail/30 bg-fail/[0.06] px-4 py-3 sm:flex-row sm:items-center'
          : 'flex flex-col gap-3 rounded-xl border border-warning/30 bg-warning/[0.06] px-4 py-3 sm:flex-row sm:items-center'
      }
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Icon className={offline ? 'mt-0.5 size-4 shrink-0 text-fail' : 'mt-0.5 size-4 shrink-0 text-warning'} aria-hidden />
        <div className="min-w-0 text-sm">
          <p className="font-medium text-fg">
            {offline ? 'The PréMoulinette server is not reachable' : 'No sandbox is ready: analyses cannot run your code yet'}
          </p>
          <p className="mt-0.5 text-fg-muted">
            {offline
              ? 'Double-click start.bat (keep its black window open), then reload this page.'
              : status.description}
          </p>
        </div>
      </div>
      {!offline && (
        <Link
          to="/settings"
          className="group inline-flex shrink-0 items-center gap-1 self-start rounded-md border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-xs font-medium text-warning hover:bg-warning/15 sm:self-auto"
        >
          Open settings
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      )}
    </div>
  )
}
