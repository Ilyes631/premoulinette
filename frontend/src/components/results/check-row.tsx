import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { ProvenanceBadge } from '@/components/ui/provenance-badge'
import { SeverityBadge } from '@/components/ui/severity-badge'
import { StatusIcon } from '@/components/ui/status-badge'
import { cn } from '@/lib/cn'
import { formatLocation } from '@/lib/format'
import type { CheckResult } from '@/lib/types'

export interface CheckRowProps {
  check: CheckResult
  selected?: boolean
  onSelect?: (check: CheckResult) => void
  className?: string
}

export function checkLocationLabel(check: CheckResult): string | null {
  if (check.location) return formatLocation(check.location)
  return check.file ? formatLocation({ file: check.file, line: null }) : null
}

/** Compact, keyboard-accessible row: status icon, title, message, file:line and badges. */
export function CheckRow({ check, selected = false, onSelect, className }: CheckRowProps) {
  const where = checkLocationLabel(check)
  const showSeverity = check.severity && (check.status === 'fail' || check.status === 'warning')
  const showProvenance = check.origin.provenance !== 'explicit'
  return (
    <button
      type="button"
      onClick={() => onSelect?.(check)}
      aria-current={selected || undefined}
      data-status={check.status}
      className={cn(
        'group flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors duration-150',
        'hover:bg-surface-2 aria-[current=true]:bg-surface-2 aria-[current=true]:shadow-[inset_2px_0_0_var(--pm-accent)]',
        className,
      )}
    >
      <StatusIcon status={check.status} className="mt-0.5" />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium text-fg">{check.title}</span>
          {check.bonus && (
            <Badge tone="bonus" variant="outline" className="hidden sm:inline-flex">
              Bonus
            </Badge>
          )}
          {!check.mandatory && !check.bonus && check.status !== 'pass' && (
            <Badge variant="outline" className="hidden sm:inline-flex">
              Optional
            </Badge>
          )}
        </span>
        <span className="line-clamp-2 text-xs text-fg-muted sm:truncate">{check.message}</span>
        <span className="mt-1 flex flex-wrap items-center gap-1.5 sm:hidden">
          {where && <span className="font-mono text-2xs text-fg-subtle">{where}</span>}
          {showSeverity && check.severity && <SeverityBadge severity={check.severity} />}
          {showProvenance && <ProvenanceBadge provenance={check.origin.provenance} confidence={check.origin.confidence} />}
        </span>
      </span>
      <span className="hidden shrink-0 items-center gap-1.5 pt-0.5 sm:flex">
        {where && <span className="max-w-40 truncate font-mono text-2xs text-fg-subtle">{where}</span>}
        {showProvenance && <ProvenanceBadge provenance={check.origin.provenance} confidence={check.origin.confidence} />}
        {showSeverity && check.severity && <SeverityBadge severity={check.severity} />}
      </span>
      <ChevronRight
        className="mt-0.5 size-4 shrink-0 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
        aria-hidden
      />
    </button>
  )
}
