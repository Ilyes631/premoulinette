import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ReactElement, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export const TooltipProvider = TooltipPrimitive.Provider

export interface TooltipProps {
  content: ReactNode
  /** A single element able to hold a ref (button, span...). */
  children: ReactElement
  side?: 'top' | 'right' | 'bottom' | 'left'
  align?: 'start' | 'center' | 'end'
  className?: string
  delayDuration?: number
}

/** Hover/focus tooltip. Renders the child untouched when `content` is empty. */
export function Tooltip({ content, children, side = 'top', align = 'center', className, delayDuration }: TooltipProps) {
  if (content === null || content === undefined || content === '') return children
  return (
    <TooltipPrimitive.Root delayDuration={delayDuration}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            'z-50 max-w-72 rounded-md border border-border-strong bg-surface-3 px-2 py-1.5 text-xs leading-snug text-fg shadow-pop',
            'animate-pop-in data-[state=closed]:animate-pop-out',
            className,
          )}
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}
