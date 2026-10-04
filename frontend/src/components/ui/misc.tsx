/** Small presentational primitives: Kbd, Skeleton, Spinner, Input, Separator. */
import { LoaderCircle } from 'lucide-react'
import type { HTMLAttributes, InputHTMLAttributes, Ref } from 'react'
import { cn } from '@/lib/cn'

export function Kbd({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      className={cn(
        'inline-flex h-5 min-w-5 items-center justify-center rounded border border-border-strong bg-surface-2 px-1',
        'font-mono text-2xs font-medium text-fg-muted shadow-[inset_0_-1px_0_var(--pm-border-strong)]',
        className,
      )}
      {...props}
    />
  )
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn('animate-pulse rounded-md bg-fg/5', className)} {...props} />
}

export function Spinner({ className, label = 'Loading' }: { className?: string; label?: string }) {
  return <LoaderCircle className={cn('size-4 animate-spin text-fg-muted', className)} role="img" aria-label={label} />
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  ref?: Ref<HTMLInputElement>
  invalid?: boolean
}

export function Input({ className, invalid, ref, ...props }: InputProps) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'h-9 w-full min-w-0 rounded-lg border border-border-strong bg-bg-subtle px-3 text-sm text-fg shadow-[inset_0_1px_2px_var(--pm-shadow)]',
        'placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-150',
        'focus-visible:border-accent focus-visible:shadow-[0_0_0_3px_color-mix(in_oklab,var(--pm-accent)_25%,transparent)] focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-50',
        invalid && 'border-fail/60',
        className,
      )}
      {...props}
    />
  )
}

export function Separator({ className, vertical = false }: { className?: string; vertical?: boolean }) {
  return (
    <div
      role="separator"
      aria-orientation={vertical ? 'vertical' : 'horizontal'}
      className={cn('shrink-0 bg-border', vertical ? 'h-full w-px' : 'h-px w-full', className)}
    />
  )
}
