import { History, ScanSearch, Settings, type LucideIcon } from 'lucide-react'
import { MotionConfig } from 'motion/react'
import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { DemoBanner } from '@/components/demo/demo-banner'
import { ThemeToggle } from '@/components/ui'
import { cn } from '@/lib/cn'
import { IS_DEMO } from '@/lib/demo/config'
import { LogoMark } from './logo'
import { SandboxPill } from './sandbox-pill'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  /** Other routes that belong to this section (keeps the tab active while analyzing). */
  also?: RegExp
}

const NAV: NavItem[] = [
  { to: '/', label: 'Analyze', icon: ScanSearch, end: true, also: /^\/(jobs|subjects)\// },
  { to: '/history', label: 'History', icon: History, also: /^\/analyses\// },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const MAIN_CONTENT_ID = 'main-content'

/** Application chrome: sticky translucent top bar, page container, footer. */
export function AppShell() {
  const { pathname } = useLocation()

  // New page: start at the top (the browser keeps the scroll position of SPA navigations otherwise).
  useEffect(() => {
    if (typeof window.scrollTo === 'function') {
      try {
        window.scrollTo({ top: 0 })
      } catch {
        // jsdom / old browsers
      }
    }
  }, [pathname])

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative isolate flex min-h-dvh flex-col bg-bg text-fg">
        <a
          href={`#${MAIN_CONTENT_ID}`}
          className="sr-only z-50 rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-contrast shadow-pop focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>

        {/* Very restrained ambient background: accent glow + fading dot grid. */}
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[34rem] overflow-hidden">
          <div className="surface-glow absolute inset-0" />
          <div className="bg-dots absolute inset-0 opacity-50 [mask-image:radial-gradient(48rem_26rem_at_50%_0%,black,transparent_75%)]" />
        </div>

        {IS_DEMO && <DemoBanner />}

        <header className="sticky top-0 z-40 border-b border-border bg-bg/75 backdrop-blur-xl backdrop-saturate-150">
          <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-4 sm:gap-4 sm:px-6">
            <Link
              to="/"
              className="group flex shrink-0 items-center gap-2 rounded-md"
              aria-label="PréMoulinette — home"
            >
              <LogoMark className="transition-transform duration-300 ease-out group-hover:rotate-90 motion-reduce:transition-none" />
              <span className="text-sm font-semibold tracking-tight text-fg">PréMoulinette</span>
            </Link>

            <span aria-hidden className="hidden h-5 w-px bg-border-strong sm:block" />

            <nav aria-label="Main" className="flex min-w-0 items-center gap-0.5">
              {NAV.map((item) => (
                <ShellNavLink key={item.to} item={item} pathname={pathname} />
              ))}
            </nav>

            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <SandboxPill />
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main
          id={MAIN_CONTENT_ID}
          tabIndex={-1}
          className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 outline-none sm:px-6 sm:py-10"
        >
          <Outlet />
        </main>

        <footer className="border-t border-border">
          <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-1 px-4 py-5 text-center text-xs text-fg-subtle sm:flex-row sm:px-6 sm:text-left">
            <p>
              Readiness Score is not an official grade <span aria-hidden>·</span>{' '}
              {IS_DEMO ? 'Online demo: nothing is uploaded, no code runs' : 'Everything runs locally'}
            </p>
            <p className="hidden sm:block">PréMoulinette</p>
          </div>
        </footer>
      </div>
    </MotionConfig>
  )
}

function ShellNavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const Icon = item.icon
  const sectionActive = item.also?.test(pathname) ?? false
  return (
    <NavLink
      to={item.to}
      end={item.end}
      aria-label={item.label}
      className={({ isActive }) => {
        const active = isActive || sectionActive
        return cn(
          'relative inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-sm font-medium transition-colors duration-150 sm:px-2.5',
          active ? 'bg-surface-2 text-fg shadow-card' : 'text-fg-muted hover:bg-surface-2/60 hover:text-fg',
        )
      }}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <span className="hidden sm:inline">{item.label}</span>
    </NavLink>
  )
}
