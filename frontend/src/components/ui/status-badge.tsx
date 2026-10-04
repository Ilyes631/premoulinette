import { CircleCheck, CircleSlash, CircleX, Info, Sparkles, TriangleAlert, type LucideIcon } from 'lucide-react'
import { STATUS_LABELS, STATUS_TONES } from '@/lib/check-meta'
import { cn } from '@/lib/cn'
import type { Status } from '@/lib/types'
import { Badge } from './badge'

export const STATUS_ICONS: Record<Status, LucideIcon> = {
  pass: CircleCheck,
  fail: CircleX,
  warning: TriangleAlert,
  info: Info,
  bonus: Sparkles,
  skipped: CircleSlash,
}

const STATUS_TEXT: Record<Status, string> = {
  pass: 'text-pass',
  fail: 'text-fail',
  warning: 'text-warning',
  info: 'text-info',
  bonus: 'text-bonus',
  skipped: 'text-skipped',
}

export interface StatusIconProps {
  status: Status
  className?: string
  /** Screen-reader label; defaults to the status name. Pass "" for decorative use. */
  label?: string
}

export function StatusIcon({ status, className, label }: StatusIconProps) {
  const Icon = STATUS_ICONS[status]
  const text = label ?? STATUS_LABELS[status]
  return (
    <Icon
      className={cn('size-4 shrink-0', STATUS_TEXT[status], className)}
      role={text ? 'img' : undefined}
      aria-label={text || undefined}
      aria-hidden={text ? undefined : true}
    />
  )
}

export interface StatusBadgeProps {
  status: Status
  size?: 'sm' | 'md'
  className?: string
  /** Override the label (e.g. "Not implemented" for a bonus). */
  label?: string
}

export function StatusBadge({ status, size = 'sm', className, label }: StatusBadgeProps) {
  const Icon = STATUS_ICONS[status]
  return (
    <Badge tone={STATUS_TONES[status]} size={size} className={className}>
      <Icon aria-hidden />
      {label ?? STATUS_LABELS[status]}
    </Badge>
  )
}
