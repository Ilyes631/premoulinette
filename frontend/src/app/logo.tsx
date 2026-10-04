import { useId } from 'react'
import { cn } from '@/lib/cn'

/**
 * PréMoulinette mark: a four-blade mill (the "moulinette") whose blades fade like a progress sweep.
 * Same geometry as public/favicon.svg.
 */
export function LogoMark({ className }: { className?: string }) {
  const gradientId = useId()
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden className={cn('size-6 shrink-0', className)}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--pm-accent-hover)" />
          <stop offset="1" stopColor="var(--pm-accent)" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${gradientId})`} />
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="white" strokeOpacity="0.18" />
      <g fill="white">
        <path d="M16 16V7.5a5 5 0 0 1 5 5V16Z" />
        <path d="M16 16h8.5a5 5 0 0 1-5 5H16Z" opacity=".78" />
        <path d="M16 16v8.5a5 5 0 0 1-5-5V16Z" opacity=".56" />
        <path d="M16 16H7.5a5 5 0 0 1 5-5H16Z" opacity=".34" />
      </g>
      <circle cx="16" cy="16" r="1.6" fill="var(--pm-accent)" />
    </svg>
  )
}
