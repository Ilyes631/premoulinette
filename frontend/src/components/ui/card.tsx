import type { HTMLAttributes, Ref } from 'react'
import { cn } from '@/lib/cn'

type DivProps = HTMLAttributes<HTMLDivElement> & { ref?: Ref<HTMLDivElement> }

export function Card({ className, ...props }: DivProps) {
  return <div className={cn('rounded-xl border border-border bg-surface shadow-card', className)} {...props} />
}

export function CardHeader({ className, ...props }: DivProps) {
  return <div className={cn('flex flex-col gap-1 px-5 pt-5 pb-3', className)} {...props} />
}

export function CardTitle({
  className,
  as: Tag = 'h3',
  ...props
}: HTMLAttributes<HTMLHeadingElement> & { as?: 'h2' | 'h3' | 'h4' }) {
  return <Tag className={cn('text-sm font-semibold tracking-tight text-fg', className)} {...props} />
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm text-fg-muted', className)} {...props} />
}

export function CardContent({ className, ...props }: DivProps) {
  return <div className={cn('px-5 pb-5', className)} {...props} />
}

export function CardFooter({ className, ...props }: DivProps) {
  return (
    <div
      className={cn('flex items-center gap-2 border-t border-border px-5 py-3', className)}
      {...props}
    />
  )
}
