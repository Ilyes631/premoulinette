import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes, Ref } from 'react'
import { cn } from '@/lib/cn'

export const badgeVariants = cva(
  'inline-flex shrink-0 items-center whitespace-nowrap rounded-md border font-medium leading-none [&_svg]:shrink-0',
  {
    variants: {
      tone: {
        neutral: 'border-border-strong bg-surface-2 text-fg-muted',
        accent: 'border-accent-fg/30 bg-accent/15 text-accent-fg',
        pass: 'border-pass/25 bg-pass/10 text-pass',
        fail: 'border-fail/25 bg-fail/10 text-fail',
        warning: 'border-warning/25 bg-warning/10 text-warning',
        info: 'border-info/25 bg-info/10 text-info',
        bonus: 'border-bonus/25 bg-bonus/10 text-bonus',
        skipped: 'border-skipped/25 bg-skipped/10 text-skipped',
      },
      variant: {
        soft: '',
        outline: 'bg-transparent',
        dashed: 'border-dashed bg-transparent',
        solid: 'border-transparent bg-fg/90 text-bg',
      },
      size: {
        sm: 'h-5 gap-1 px-1.5 text-2xs [&_svg]:size-3',
        md: 'h-6 gap-1.5 px-2 text-xs [&_svg]:size-3.5',
      },
    },
    defaultVariants: { tone: 'neutral', variant: 'soft', size: 'sm' },
  },
)

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  ref?: Ref<HTMLSpanElement>
}

export function Badge({ className, tone, variant, size, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone, variant, size }), className)} {...props} />
}
