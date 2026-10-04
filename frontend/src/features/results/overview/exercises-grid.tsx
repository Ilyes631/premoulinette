import { LayoutGrid } from 'lucide-react'
import { Badge, ProgressBar, scoreTone } from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatPercent } from '@/lib/format'
import type { ExerciseScore } from '@/lib/types'
import { exerciseStatusMeta } from '../shared/meta'
import { SectionCard } from '../shared/section-card'

interface ExercisesGridProps {
  exercises: ExerciseScore[]
  onSelect?: (exercise: ExerciseScore) => void
}

export function ExercisesGrid({ exercises, onSelect }: ExercisesGridProps) {
  const mandatory = exercises.filter((e) => !e.bonus)
  const bonus = exercises.filter((e) => e.bonus)
  return (
    <SectionCard
      icon={LayoutGrid}
      title="Exercises"
      description={`${mandatory.length} mandatory · ${bonus.length} bonus`}
    >
      {exercises.length === 0 ? (
        <p className="py-6 text-center text-sm text-fg-muted">The subject defines no exercise.</p>
      ) : (
        <ul className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {[...mandatory, ...bonus].map((ex) => (
            <li key={ex.exercise_id}>
              <ExerciseCard exercise={ex} onSelect={onSelect} />
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}

function ExerciseCard({ exercise: ex, onSelect }: { exercise: ExerciseScore; onSelect?: (e: ExerciseScore) => void }) {
  const meta = exerciseStatusMeta(ex)
  const notImplemented = ex.bonus && ex.status === 'not_implemented'
  const tone = scoreTone(ex.score)
  return (
    <button
      type="button"
      onClick={() => onSelect?.(ex)}
      aria-label={`${ex.title}: ${meta.label}${ex.score !== null ? `, ${formatPercent(ex.score)}` : ''}. Show its issues`}
      className={cn(
        'group flex h-full w-full flex-col gap-2.5 rounded-lg border bg-surface-2/40 p-3 text-left transition-colors hover:bg-surface-2',
        ex.bonus ? 'border-dashed border-bonus/30' : 'border-border',
      )}
    >
      <span className="flex items-start gap-2">
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">{ex.title}</span>
          <span className="block truncate font-mono text-2xs text-fg-subtle">{ex.file}</span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1">
          <span className="flex gap-1">
            {ex.bonus && (
              <Badge tone="bonus" variant="outline">
                BONUS
              </Badge>
            )}
            <Badge tone={meta.tone}>{meta.label}</Badge>
          </span>
        </span>
      </span>
      {notImplemented ? (
        <span className="text-xs text-fg-muted">
          Not implemented · <span className="text-fg-subtle">Impact on mandatory score: none</span>
        </span>
      ) : (
        <span className="flex items-center gap-2.5">
          <ProgressBar
            value={ex.score ?? 0}
            tone={ex.bonus ? 'bonus' : tone === 'neutral' ? 'accent' : tone}
            size="xs"
            label={`${ex.title} score`}
          />
          <span className="shrink-0 text-xs text-fg-muted tabular">
            {ex.total > 0 ? `${ex.passed}/${ex.total}` : '—'}
          </span>
          <span className="w-10 shrink-0 text-right text-xs font-medium text-fg tabular">{formatPercent(ex.score)}</span>
        </span>
      )}
      {ex.issues > 0 && (
        <span className="text-2xs text-fg-subtle">
          {ex.issues} {ex.issues === 1 ? 'issue' : 'issues'}
        </span>
      )}
    </button>
  )
}
