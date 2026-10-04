import * as DialogPrimitive from '@radix-ui/react-dialog'
import type { ComponentProps, HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'
import { CloseButton, DialogOverlay } from './dialog'

/** Side drawer built on the Radix Dialog (focus trap, Esc, scroll lock). */
export const Sheet = DialogPrimitive.Root
export const SheetTrigger = DialogPrimitive.Trigger
export const SheetClose = DialogPrimitive.Close
export const SheetTitle = DialogPrimitive.Title
export const SheetDescription = DialogPrimitive.Description

export interface SheetContentProps extends ComponentProps<typeof DialogPrimitive.Content> {
  /** Tailwind max-width class for the panel. */
  widthClassName?: string
}

export function SheetContent({ className, children, widthClassName = 'sm:max-w-2xl', ...props }: SheetContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogOverlay className="bg-black/45" />
      <DialogPrimitive.Content
        className={cn(
          'fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-border-strong bg-surface shadow-pop outline-none',
          'animate-sheet-in data-[state=closed]:animate-sheet-out',
          widthClassName,
          className,
        )}
        {...props}
      >
        {children}
        <CloseButton className="absolute top-3 right-3" />
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export function SheetHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-b border-border px-5 py-4 pr-14', className)} {...props} />
}

export function SheetBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('min-h-0 flex-1 overflow-y-auto overscroll-contain', className)} {...props} />
}
