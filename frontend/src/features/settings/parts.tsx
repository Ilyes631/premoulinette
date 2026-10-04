import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui'
import { cn } from '@/lib/cn'

export function SettingsSection({
  icon: Icon,
  title,
  description,
  children,
  id,
}: {
  icon: LucideIcon
  title: string
  description: ReactNode
  children: ReactNode
  id?: string
}) {
  const headingId = id ? `${id}-title` : undefined
  return (
    <Card aria-labelledby={headingId} role="region">
      <div className="flex items-start gap-3 border-b border-border px-5 py-4">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border-strong bg-surface-2 text-fg-muted">
          <Icon className="size-4" aria-hidden />
        </div>
        <div className="min-w-0">
          <h2 id={headingId} className="text-sm font-semibold text-fg">
            {title}
          </h2>
          <p className="mt-0.5 text-sm text-pretty text-fg-muted">{description}</p>
        </div>
      </div>
      <div className="space-y-5 px-5 py-5">{children}</div>
    </Card>
  )
}

export interface RadioCardOption<T extends string> {
  value: T
  title: ReactNode
  description: ReactNode
  badge?: ReactNode
}

/** Accessible radio group rendered as selectable cards (native radios, arrow keys work). */
export function RadioCards<T extends string>({
  name,
  legend,
  value,
  options,
  onChange,
  columns = 3,
}: {
  name: string
  legend: string
  value: T
  options: Array<RadioCardOption<T>>
  onChange: (value: T) => void
  columns?: 2 | 3
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-xs font-medium text-fg-muted">{legend}</legend>
      <div className={cn('grid gap-2', columns === 3 ? 'md:grid-cols-3' : 'sm:grid-cols-2')}>
        {options.map((option) => {
          const checked = option.value === value
          const titleId = `${name}-${option.value}-title`
          const descriptionId = `${name}-${option.value}-description`
          return (
            <label
              key={option.value}
              className={cn(
                'relative flex cursor-pointer flex-col gap-1 rounded-lg border px-3.5 py-3 transition-colors',
                'has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring',
                checked ? 'border-accent/60 bg-accent/8' : 'border-border-strong bg-surface-2/40 hover:bg-surface-2',
              )}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name={name}
                  value={option.value}
                  checked={checked}
                  onChange={() => onChange(option.value)}
                  aria-labelledby={titleId}
                  aria-describedby={descriptionId}
                  className="size-3.5 accent-accent"
                />
                <span id={titleId} className="text-sm font-medium text-fg">
                  {option.title}
                </span>
                {option.badge && <span className="ml-auto">{option.badge}</span>}
              </span>
              <span id={descriptionId} className="pl-5.5 text-xs text-pretty text-fg-muted">
                {option.description}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <p role="alert" className="mt-1.5 text-xs text-fail">
      {message}
    </p>
  )
}
