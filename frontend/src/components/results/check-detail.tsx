import { BookOpen, CircleSlash, FileCode, Lightbulb, WandSparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ProvenanceBadge } from '@/components/ui/provenance-badge'
import { SeverityBadge } from '@/components/ui/severity-badge'
import { StatusBadge } from '@/components/ui/status-badge'
import { CATEGORY_LABELS } from '@/lib/check-meta'
import { formatLocation } from '@/lib/format'
import type { CheckResult, ExplainMode, Location } from '@/lib/types'
import { EvidenceView } from './evidence-view'
import { ExplanationPanel, type ExplanationState } from './explanation-panel'
import { FixPreview } from './fix-preview'
import { ProvenanceLine } from './provenance-line'

export interface CheckDetailProps {
  check: CheckResult
  /** Opens the student file at a location (source viewer). */
  onOpenSource?: (location: Location) => void
  /** Requests an explanation: "explain", "fix" (how to fix) or "expected" (expected behavior). */
  onExplain?: (mode: ExplainMode) => void
  explanation?: ExplanationState | null
  /** Jump to another check (used for `blocked_by`). */
  onSelectCheck?: (checkId: string) => void
  /** Title of the blocking check, when known. */
  blockedByTitle?: string
}

export function checkSourceLocation(check: CheckResult): Location | null {
  if (check.location) return check.location
  return check.file ? { file: check.file, line: null, end_line: null, col: null } : null
}

/** Full detail of one check: verdict, provenance, evidence, suggested fix and explanation actions. */
export function CheckDetail({ check, onOpenSource, onExplain, explanation, onSelectCheck, blockedByTitle }: CheckDetailProps) {
  const source = checkSourceLocation(check)
  const busy = explanation?.status === 'loading'
  const explainButton = (mode: ExplainMode, label: string, Icon: typeof Lightbulb) => (
    <Button
      size="sm"
      variant={explanation?.mode === mode ? 'outline' : 'secondary'}
      disabled={!onExplain || (busy && explanation?.mode !== mode)}
      loading={busy && explanation?.mode === mode}
      onClick={() => onExplain?.(mode)}
      aria-pressed={explanation?.mode === mode}
    >
      {!(busy && explanation?.mode === mode) && <Icon aria-hidden />}
      {label}
    </Button>
  )

  return (
    <article className="space-y-6" aria-labelledby={`check-title-${check.id}`}>
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={check.status} size="md" />
          {check.severity && check.status !== 'pass' && <SeverityBadge severity={check.severity} size="md" />}
          <ProvenanceBadge provenance={check.origin.provenance} confidence={check.origin.confidence} />
          <Badge variant="outline">{CATEGORY_LABELS[check.category]}</Badge>
          {check.bonus && <Badge tone="bonus">Bonus</Badge>}
          {!check.mandatory && !check.bonus && <Badge variant="dashed">Not counted in readiness</Badge>}
        </div>
        <h2 id={`check-title-${check.id}`} className="text-lg font-semibold tracking-tight text-fg">
          {check.title}
        </h2>
        {source && (
          <p className="font-mono text-xs text-fg-subtle">
            {formatLocation(source, true)}
            {check.function && <span> · {check.function}()</span>}
          </p>
        )}
        <p className="text-sm leading-relaxed text-pretty text-fg">{check.message}</p>
        <ProvenanceLine origin={check.origin} />
      </header>

      {check.blocked_by && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-skipped/25 bg-skipped/5 px-3 py-2.5 text-sm text-fg-muted">
          <CircleSlash className="size-4 text-skipped" aria-hidden />
          <span>This check could not run because another check failed first.</span>
          {onSelectCheck ? (
            <Button variant="link" size="sm" onClick={() => onSelectCheck(check.blocked_by as string)}>
              Go to “{blockedByTitle ?? check.blocked_by}”
            </Button>
          ) : (
            <code className="font-mono text-xs">{check.blocked_by}</code>
          )}
        </div>
      )}

      {check.evidence && <EvidenceView check={check} evidence={check.evidence} onOpenSource={onOpenSource} />}

      {check.fix && <FixPreview fix={check.fix} />}

      <div className="space-y-3 border-t border-border pt-4">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Help with this check">
          {explainButton('explain', 'Explain', Lightbulb)}
          {explainButton('fix', 'How to fix', WandSparkles)}
          {explainButton('expected', 'Show expected behavior', BookOpen)}
          <Button size="sm" variant="ghost" disabled={!onOpenSource || !source} onClick={() => source && onOpenSource?.(source)}>
            <FileCode aria-hidden /> Open file
          </Button>
        </div>
        {explanation && <ExplanationPanel state={explanation} />}
      </div>
    </article>
  )
}
