import { Info, Sparkles, Target } from 'lucide-react'
import { Card, ProgressBar, ScoreRing, scoreTone, Stat, Tooltip } from '@/components/ui'
import { formatPercent } from '@/lib/format'
import type { Confidence, ScoreSummary } from '@/lib/types'

const CONFIDENCE_META: Record<Confidence, { label: string; tone: 'pass' | 'warning' | 'fail' }> = {
  high: { label: 'High', tone: 'pass' },
  medium: { label: 'Medium', tone: 'warning' },
  low: { label: 'Low', tone: 'fail' },
}

/** Big readiness number: share of mandatory checks that pass. */
export function ReadinessHero({ score }: { score: ScoreSummary }) {
  const tone = scoreTone(score.readiness)
  return (
    <Card className="relative overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0 surface-glow opacity-60" />
      <div className="relative flex flex-col items-center gap-6 p-5 sm:flex-row sm:items-center sm:p-6">
        <ScoreRing value={score.readiness} size={148} stroke={11} label="Readiness score" caption="readiness" />
        <div className="w-full min-w-0 flex-1 space-y-4">
          <div>
            <p className="text-2xs font-semibold tracking-[0.14em] text-fg-subtle uppercase">Readiness score</p>
            <p className="mt-1 text-5xl font-semibold tracking-tight text-fg tabular" data-testid="readiness-value">
              {formatPercent(score.readiness, 1)}
            </p>
          </div>
          <ProgressBar
            value={score.readiness}
            tone={tone === 'neutral' ? 'accent' : tone}
            size="md"
            label="Readiness"
          />
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div className="flex items-baseline justify-between gap-2 border-b border-border pb-1.5">
              <dt className="text-fg-muted">Mandatory checks</dt>
              <dd className="font-medium text-fg tabular">
                {score.mandatory_passed} / {score.mandatory_total}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2 border-b border-border pb-1.5">
              <dt className="text-fg-muted">Bonus</dt>
              <dd className="font-medium text-fg tabular">
                {score.bonus_total > 0 ? `${score.bonus_passed} / ${score.bonus_total}` : '—'}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-fg-subtle">
            Share of the mandatory checks (structure, compilation, functions, tests, constraints, Git) that pass. Bonus
            and heuristic checks never lower it.
          </p>
        </div>
      </div>
    </Card>
  )
}

export function ScoreTiles({ score }: { score: ScoreSummary }) {
  const confidence = CONFIDENCE_META[score.confidence]
  const reasons = score.confidence_reasons
  return (
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
      <Stat
        icon={Target}
        label="Mandatory readiness"
        value={formatPercent(score.mandatory_readiness, 1)}
        tone={scoreTone(score.mandatory_readiness) === 'pass' ? 'pass' : score.mandatory_failures ? 'fail' : 'neutral'}
        hint={`${score.mandatory_passed} / ${score.mandatory_total} checks · ${score.mandatory_failures} failing`}
      />
      <Stat
        icon={Sparkles}
        label="Bonus completion"
        value={score.bonus_completion === null ? '—' : formatPercent(score.bonus_completion)}
        tone="bonus"
        hint={
          score.bonus_total > 0
            ? `${score.bonus_passed} / ${score.bonus_total} bonus exercises · never affects readiness`
            : 'No bonus in this subject'
        }
      />
      <Stat
        label={
          <span className="inline-flex items-center gap-1.5">
            Confidence
            <Tooltip
              content={
                reasons.length ? (
                  <ul className="list-disc space-y-1 pl-4">
                    {reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                ) : (
                  'Every check comes from explicit, reviewed requirements.'
                )
              }
            >
              <button
                type="button"
                className="inline-flex size-4 items-center justify-center rounded-full text-fg-subtle hover:text-fg"
                aria-label={`Why is confidence ${confidence.label.toLowerCase()}?`}
              >
                <Info className="size-3.5" aria-hidden />
              </button>
            </Tooltip>
          </span>
        }
        value={confidence.label}
        tone={confidence.tone}
        hint={reasons[0] ?? 'Based on explicit, reviewed requirements'}
      />
    </div>
  )
}
