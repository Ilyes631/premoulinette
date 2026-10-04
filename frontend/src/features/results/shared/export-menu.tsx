import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { ChevronDown, Download } from 'lucide-react'
import { Button } from '@/components/ui'
import { api } from '@/lib/api'
import { cn } from '@/lib/cn'
import { EXPORT_FORMATS } from './meta'

/** "Export ▾" dropdown: plain download links to GET /api/analyses/{id}/export?format=... */
export function ExportMenu({ analysisId, className }: { analysisId: string; className?: string }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button variant="secondary" className={className} aria-label="Export report">
          <Download aria-hidden />
          <span className="hidden sm:inline">Export</span>
          <ChevronDown className="opacity-60" aria-hidden />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          collisionPadding={8}
          className="z-50 min-w-56 rounded-lg border border-border-strong bg-surface-2 p-1 shadow-pop animate-pop-in"
        >
          <DropdownMenu.Label className="px-2 pt-1.5 pb-1 text-2xs font-semibold tracking-wider text-fg-subtle uppercase">
            Download report
          </DropdownMenu.Label>
          {EXPORT_FORMATS.map(({ format, label, hint, icon: Icon }) => (
            <DropdownMenu.Item key={format} asChild>
              <a
                href={api.exportUrl(analysisId, format)}
                download
                className={cn(
                  'flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-fg outline-none',
                  'data-[highlighted]:bg-surface-3',
                )}
              >
                <Icon className="size-4 text-fg-muted" aria-hidden />
                <span className="flex flex-col">
                  <span className="font-medium">{label}</span>
                  <span className="text-2xs text-fg-subtle">{hint}</span>
                </span>
              </a>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

/** Inline export buttons (report tab). */
export function ExportButtons({ analysisId }: { analysisId: string }) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Export report">
      {EXPORT_FORMATS.map(({ format, label, icon: Icon }) => (
        <a
          key={format}
          href={api.exportUrl(analysisId, format)}
          download
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border-strong bg-surface-2 px-2.5 text-xs font-medium text-fg shadow-card transition-colors hover:bg-surface-3"
        >
          <Icon className="size-3.5 text-fg-muted" aria-hidden />
          {label}
        </a>
      ))}
    </div>
  )
}
