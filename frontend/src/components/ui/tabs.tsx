import * as TabsPrimitive from '@radix-ui/react-tabs'
import { createContext, useContext, type ComponentProps } from 'react'
import { cn } from '@/lib/cn'

type TabsVariant = 'segmented' | 'underline'
const VariantContext = createContext<TabsVariant>('segmented')

export const Tabs = TabsPrimitive.Root

export function TabsList({
  className,
  variant = 'segmented',
  ...props
}: ComponentProps<typeof TabsPrimitive.List> & { variant?: TabsVariant }) {
  return (
    <VariantContext.Provider value={variant}>
      <TabsPrimitive.List
        className={cn(
          variant === 'segmented'
            ? 'inline-flex items-center gap-0.5 rounded-lg border border-border bg-bg-subtle p-0.5'
            : 'flex items-center gap-4 border-b border-border',
          className,
        )}
        {...props}
      />
    </VariantContext.Provider>
  )
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  const variant = useContext(VariantContext)
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'inline-flex min-w-0 items-center justify-center gap-1.5 whitespace-nowrap text-sm font-medium text-fg-muted transition-colors duration-150',
        'hover:text-fg disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
        variant === 'segmented'
          ? 'h-8 rounded-md px-3 data-[state=active]:bg-surface-3 data-[state=active]:text-fg data-[state=active]:shadow-card'
          : '-mb-px h-10 border-b-2 border-transparent px-0.5 data-[state=active]:border-accent data-[state=active]:text-fg',
        className,
      )}
      {...props}
    />
  )
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content className={cn('outline-none', className)} {...props} />
}
