import { ChartNoAxesColumn } from 'lucide-react'
import { ProgressBar, scoreTone } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { CategoryScore } from '@/lib/types'
import { SectionCard } from '../shared/section-card'

export function CategoryBars({ categories }: { categories: CategoryScore[] }) {
  return (
    <SectionCard
      icon={ChartNoAxesColumn}
      title="By category"
      description="Mandatory checks only. Heuristic cases are reported as warnings and not counted."
    >
      {categories.length === 0 ? (
        <p className="py-6 text-center text-sm text-fg-muted">No category could be scored.</p>
      ) : (
        <ul className="space-y-3">
          {categories.map((cat) => {
            const empty = cat.total === 0
            const tone = scoreTone(cat.score)
            return (
              <li key={cat.key} className="grid grid-cols-[minmax(0,9.5rem)_minmax(0,1fr)_auto] items-center gap-3">
                <span className={cn('truncate text-sm', empty ? 'text-fg-subtle' : 'text-fg')}>{cat.label}</span>
                {empty ? (
                  <span className="h-1.5 rounded-full border border-dashed border-border-strong" aria-hidden />
                ) : (
                  <ProgressBar
                    value={cat.score ?? 0}
                    tone={tone === 'neutral' ? 'accent' : tone}
                    label={`${cat.label}: ${cat.passed} of ${cat.total} passed`}
                  />
                )}
                <span className="flex min-w-16 items-baseline justify-end gap-1.5 text-xs tabular">
                  {empty ? (
                    <span className="text-fg-subtle">n/a</span>
                  ) : (
                    <>
                      <span className={cn('font-medium', cat.failed ? 'text-fail' : 'text-fg')}>{cat.passed}</span>
                      <span className="text-fg-subtle">/ {cat.total}</span>
                    </>
                  )}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </SectionCard>
  )
}
