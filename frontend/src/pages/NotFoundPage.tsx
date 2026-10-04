import { ArrowLeft, History } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { buttonVariants } from '@/components/ui'

export function NotFoundPage() {
  const { pathname } = useLocation()
  return (
    <section aria-labelledby="not-found-title" className="flex flex-col items-center py-16 text-center sm:py-24">
      <p className="tabular bg-gradient-to-b from-fg/80 to-fg/10 bg-clip-text font-mono text-7xl font-semibold tracking-tighter text-transparent sm:text-8xl">
        404
      </p>
      <h1 id="not-found-title" className="mt-4 text-xl font-semibold tracking-tight text-fg">
        Page not found
      </h1>
      <p className="mt-2 max-w-sm text-sm text-pretty text-fg-muted">
        Nothing lives at <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-xs text-fg">{pathname}</code>.
        The link may be outdated, or the analysis was deleted.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Link to="/" className={buttonVariants({ variant: 'primary' })}>
          <ArrowLeft aria-hidden />
          Back home
        </Link>
        <Link to="/history" className={buttonVariants({ variant: 'secondary' })}>
          <History aria-hidden />
          History
        </Link>
      </div>
    </section>
  )
}
