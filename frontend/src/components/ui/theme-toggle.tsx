import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Check, Monitor, Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/cn'
import { useTheme, type ThemePreference } from '@/lib/theme'
import { Tooltip } from './tooltip'

const OPTIONS: Array<{ value: ThemePreference; label: string; Icon: typeof Sun }> = [
  { value: 'system', label: 'System', Icon: Monitor },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'light', label: 'Light', Icon: Sun },
]

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const CurrentIcon = resolvedTheme === 'dark' ? Moon : Sun
  return (
    <DropdownMenu.Root>
      <Tooltip content="Theme">
        <DropdownMenu.Trigger
          aria-label={`Theme: ${theme}`}
          className={cn(
            'inline-flex size-8 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg data-[state=open]:bg-surface-2',
            className,
          )}
        >
          <CurrentIcon className="size-4" aria-hidden />
        </DropdownMenu.Trigger>
      </Tooltip>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-50 min-w-36 rounded-lg border border-border-strong bg-surface-3 p-1 shadow-pop animate-pop-in data-[state=closed]:animate-pop-out"
        >
          <DropdownMenu.RadioGroup value={theme} onValueChange={(v) => setTheme(v as ThemePreference)}>
            {OPTIONS.map(({ value, label, Icon }) => (
              <DropdownMenu.RadioItem
                key={value}
                value={value}
                className="flex h-8 cursor-pointer items-center gap-2 rounded-md px-2 text-sm text-fg-muted outline-none select-none data-[highlighted]:bg-surface-2 data-[highlighted]:text-fg data-[state=checked]:text-fg"
              >
                <Icon className="size-4" aria-hidden />
                <span className="flex-1">{label}</span>
                <DropdownMenu.ItemIndicator>
                  <Check className="size-3.5 text-accent-fg" aria-hidden />
                </DropdownMenu.ItemIndicator>
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
