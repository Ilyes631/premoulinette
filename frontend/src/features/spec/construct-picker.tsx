import { cn } from '@/lib/cn'
import type { Construct } from '@/lib/types'
import { CONSTRUCTS } from './spec-utils'

/** Toggle buttons for Python constructs (forbidden / required). */
export function ConstructPicker({ label, values, onChange }: { label: string; values: Construct[]; onChange: (v: Construct[]) => void }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-xs font-medium text-fg-muted">{label}</legend>
      <div className="flex flex-wrap gap-1.5">
        {CONSTRUCTS.map((c) => {
          const on = values.includes(c)
          return (
            <button
              key={c}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? values.filter((v) => v !== c) : [...values, c])}
              className={cn(
                'h-7 rounded-md border px-2 font-mono text-xs transition-colors',
                on ? 'border-accent-fg/40 bg-accent/15 text-accent-fg' : 'border-border-strong text-fg-muted hover:text-fg',
              )}
            >
              {c}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
