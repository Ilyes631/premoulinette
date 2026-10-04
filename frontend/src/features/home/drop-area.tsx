import { Upload, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button, DropZone } from '@/components/ui'
import { cn } from '@/lib/cn'

export interface DropAreaProps {
  onFiles: (files: File[]) => void
  accept?: string
  directory?: boolean
  disabled?: boolean
  inputLabel: string
  icon?: LucideIcon
  title: ReactNode
  hint?: ReactNode
  browseLabel: string
  /** Shown instead of the idle content while a file is being imported. */
  busy?: ReactNode
  className?: string
}

/** Large dashed drop target with a real "browse" button (keyboard accessible). */
export function DropArea({
  onFiles,
  accept,
  directory = false,
  disabled = false,
  inputLabel,
  icon: Icon = Upload,
  title,
  hint,
  browseLabel,
  busy,
  className,
}: DropAreaProps) {
  return (
    <DropZone onFiles={onFiles} accept={accept} directory={directory} disabled={disabled || Boolean(busy)} inputLabel={inputLabel}>
      {({ dragging, browse }) => (
        <div
          className={cn(
            'flex min-h-44 flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-4 py-6 text-center transition-[border-color,background-color] duration-150',
            dragging
              ? 'border-accent bg-accent/[0.07]'
              : 'border-border-strong bg-bg-subtle/60 hover:border-fg-subtle/40',
            className,
          )}
        >
          {busy ?? (
            <>
              <div
                aria-hidden
                className={cn(
                  'flex size-10 items-center justify-center rounded-full border bg-surface-2 shadow-card transition-transform duration-200',
                  dragging ? 'scale-110 border-accent/50 text-accent-fg' : 'border-border-strong text-fg-muted',
                )}
              >
                <Icon className="size-4.5" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-fg">{dragging ? 'Release to import' : title}</p>
                {hint && <p className="text-xs text-fg-subtle">{hint}</p>}
              </div>
              <Button size="sm" variant="secondary" onClick={browse} disabled={disabled}>
                {browseLabel}
              </Button>
            </>
          )}
        </div>
      )}
    </DropZone>
  )
}
