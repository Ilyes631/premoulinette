import type { LucideIcon } from 'lucide-react'
import { useId, type ReactNode } from 'react'
import { Card } from '@/components/ui'
import { cn } from '@/lib/cn'

interface SectionCardProps {
  title: ReactNode
  icon?: LucideIcon
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  /** Accessible id for the heading (aria-labelledby). */
  id?: string
}

/** Card with a compact header row: icon · title · description … actions. */
export function SectionCard({ title, icon: Icon, description, actions, children, className, bodyClassName, id }: SectionCardProps) {
  const autoId = useId()
  const headingId = id ?? autoId
  return (
    <Card className={cn('flex min-w-0 flex-col', className)} role="region" aria-labelledby={headingId}>
      <div className="flex items-start gap-3 px-4 pt-4 pb-3 sm:px-5">
        <div className="min-w-0 flex-1">
          <h3 id={headingId} className="flex items-center gap-2 text-sm font-semibold tracking-tight text-fg">
            {Icon && <Icon className="size-4 shrink-0 text-fg-subtle" aria-hidden />}
            {title}
          </h3>
          {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
      </div>
      <div className={cn('min-w-0 flex-1 px-4 pb-4 sm:px-5', bodyClassName)}>{children}</div>
    </Card>
  )
}
