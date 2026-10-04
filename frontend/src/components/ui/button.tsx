import { cva, type VariantProps } from 'class-variance-authority'
import { LoaderCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, Ref } from 'react'
import { cn } from '@/lib/cn'

export const buttonVariants = cva(
  [
    'relative inline-flex shrink-0 select-none items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium',
    'transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out',
    'active:translate-y-px disabled:pointer-events-none disabled:opacity-45',
    '[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  ],
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-contrast shadow-button hover:bg-accent-hover',
        secondary: 'border border-border-strong bg-surface-2 text-fg shadow-card hover:bg-surface-3',
        outline: 'border border-border-strong bg-transparent text-fg hover:bg-surface-2',
        ghost: 'text-fg-muted hover:bg-surface-2 hover:text-fg',
        danger: 'border border-fail/30 bg-fail/10 text-fail hover:bg-fail/20',
        link: 'h-auto rounded-sm px-0 text-accent-fg underline-offset-4 hover:underline active:translate-y-0',
      },
      size: {
        sm: 'h-8 rounded-md px-2.5 text-xs [&_svg]:size-3.5',
        md: 'h-9 px-3.5 text-sm',
        lg: 'h-11 px-5 text-sm',
        icon: 'size-9',
        'icon-sm': 'size-8 rounded-md [&_svg]:size-3.5',
      },
    },
    compoundVariants: [{ variant: 'link', className: 'h-auto px-0' }],
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
)

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  /** Shows a spinner, disables the button and sets aria-busy. */
  loading?: boolean
  ref?: Ref<HTMLButtonElement>
}

export function Button({
  className,
  variant,
  size,
  loading = false,
  disabled,
  children,
  type = 'button',
  ref,
  ...props
}: ButtonProps) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <LoaderCircle className="animate-spin" aria-hidden />}
      {children}
    </button>
  )
}
