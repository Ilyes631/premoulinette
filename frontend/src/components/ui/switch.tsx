import * as SwitchPrimitive from '@radix-ui/react-switch'
import { useId, type ComponentProps, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface SwitchProps extends ComponentProps<typeof SwitchPrimitive.Root> {
  /** Visible label rendered next to the switch (clickable). */
  label?: ReactNode
  size?: 'sm' | 'md'
}

export function Switch({ className, label, id, size = 'md', ...props }: SwitchProps) {
  const autoId = useId()
  const switchId = id ?? autoId
  const control = (
    <SwitchPrimitive.Root
      id={switchId}
      className={cn(
        'peer inline-flex shrink-0 items-center rounded-full border border-border-strong bg-surface-3 p-px transition-colors duration-150',
        'data-[state=checked]:border-transparent data-[state=checked]:bg-accent disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-4 w-7' : 'h-5 w-9',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          'pointer-events-none block rounded-full bg-fg shadow-sm transition-transform duration-150 ease-out data-[state=checked]:bg-white',
          size === 'sm' ? 'size-3 data-[state=checked]:translate-x-3' : 'size-4 data-[state=checked]:translate-x-4',
        )}
      />
    </SwitchPrimitive.Root>
  )
  if (!label) return control
  return (
    <span className="inline-flex items-center gap-2">
      {control}
      <label htmlFor={switchId} className="cursor-pointer select-none text-xs text-fg-muted peer-hover:text-fg">
        {label}
      </label>
    </span>
  )
}
