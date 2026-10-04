import {
  BadgeCheck,
  Boxes,
  CheckCircle2,
  CircleX,
  FileCode2,
  FileText,
  FlaskConical,
  Gift,
  Languages,
  ListChecks,
  Pencil,
  ShieldBan,
  Sparkles,
  SquareFunction,
  SquareTerminal,
  TriangleAlert,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Badge,
  Button,
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Stat,
} from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatDateTime } from '@/lib/format'
import type { SpecIssue, SubjectView } from '@/lib/types'
import { countAiExtracted, exerciseIndexFromPath, isAiParser, parserLabel } from './spec-utils'

export function SpecHeader({ subject }: { subject: SubjectView }) {
  const errors = subject.validation.filter((i) => i.level === 'error').length
  const warnings = subject.warnings.length + subject.validation.filter((i) => i.level === 'warning').length
  const aiItems = countAiExtracted(subject.spec)
  const meta = subject.spec.metadata

  const status = errors
    ? { Icon: CircleX, tone: 'text-fail', text: `Subject parsed — ${errors} error${errors > 1 ? 's' : ''} to review` }
    : warnings
      ? { Icon: TriangleAlert, tone: 'text-warning', text: `Subject parsed with ${warnings} warning${warnings > 1 ? 's' : ''}` }
      : { Icon: CheckCircle2, tone: 'text-pass', text: 'Subject parsed successfully' }

  return (
    <div className="min-w-0">
      <p className={cn('flex items-center gap-1.5 text-xs font-medium', status.tone)}>
        <status.Icon className="size-3.5" aria-hidden />
        {status.text}
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-fg sm:text-[1.75rem]">{subject.title || meta.title}</h1>
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-xs text-fg-muted">
        <Badge tone={isAiParser(subject.parser) ? 'warning' : 'neutral'} size="md">
          {isAiParser(subject.parser) ? <Sparkles aria-hidden /> : <ListChecks aria-hidden />}
          {parserLabel(subject.parser)} parser
        </Badge>
        <Badge size="md" variant="outline" className="max-w-full">
          <FileText aria-hidden />
          <span className="truncate">{subject.source_name}</span>
          <span className="text-fg-subtle uppercase">{subject.media_type}</span>
        </Badge>
        {meta.reviewed_by_user ? (
          <Badge tone="pass" size="md">
            <BadgeCheck aria-hidden /> Reviewed by you
          </Badge>
        ) : (
          <Badge tone="info" size="md" variant="outline">
            Not reviewed yet
          </Badge>
        )}
        {aiItems > 0 && (
          <Badge tone="warning" size="md">
            {aiItems} AI-extracted item{aiItems > 1 ? 's' : ''} to check
          </Badge>
        )}
        {meta.course && <span className="px-1">{meta.course}</span>}
        {meta.deadline && <span className="px-1">Deadline {meta.deadline}</span>}
        <span className="px-1 text-fg-subtle">Updated {formatDateTime(subject.updated_at)}</span>
      </div>
    </div>
  )
}

export function SpecStatsGrid({ subject }: { subject: SubjectView }) {
  const s = subject.stats
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Stat label="Language" icon={Languages} value={<span className="capitalize">{s.language}</span>} hint={subject.spec.language_version ?? 'any version'} />
      <Stat label="Required files" icon={FileCode2} value={s.required_files} />
      <Stat label="Functions" icon={SquareFunction} value={s.functions} />
      <Stat label="Known tests" icon={FlaskConical} value={s.known_tests} hint="explicit examples" />
      <Stat label="Exercises" icon={Boxes} value={s.exercises} hint={`${s.mandatory_exercises} mandatory`} />
      <Stat label="Script tests" icon={SquareTerminal} value={s.script_tests} hint="terminal sessions" />
      <Stat label="Constraints" icon={ShieldBan} value={s.constraints} />
      <Stat label="Bonus exercises" icon={Gift} value={s.bonus_exercises} tone={s.bonus_exercises ? 'bonus' : 'neutral'} />
    </div>
  )
}

export function ValidationPanel({
  issues,
  warnings,
  onOpenExercise,
}: {
  issues: SpecIssue[]
  warnings: string[]
  onOpenExercise: (index: number) => void
}) {
  if (!issues.length && !warnings.length) return null
  const sorted = [...issues].sort((a, b) => Number(a.level === 'warning') - Number(b.level === 'warning'))
  return (
    <section aria-label="Validation" className="rounded-xl border border-border bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <TriangleAlert className="size-4 text-warning" aria-hidden />
        <h2 className="text-sm font-semibold text-fg">Review before analyzing</h2>
        <span className="tabular text-xs text-fg-muted">
          {issues.filter((i) => i.level === 'error').length} errors · {issues.filter((i) => i.level === 'warning').length + warnings.length} warnings
        </span>
      </header>
      <ul className="max-h-64 divide-y divide-border overflow-y-auto">
        {sorted.map((issue, i) => {
          const index = exerciseIndexFromPath(issue.path)
          return (
            <li key={`${issue.path}-${i}`} className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 py-2 text-sm">
              <Badge tone={issue.level === 'error' ? 'fail' : 'warning'}>{issue.level === 'error' ? 'Error' : 'Warning'}</Badge>
              <code className="font-mono text-2xs text-fg-subtle">{issue.path}</code>
              <span className="min-w-0 flex-1 text-fg">{issue.message}</span>
              {index !== null && (
                <Button size="sm" variant="ghost" onClick={() => onOpenExercise(index)} aria-label={`Fix ${issue.path}`}>
                  <Pencil aria-hidden /> Fix
                </Button>
              )}
            </li>
          )
        })}
        {warnings.map((w, i) => (
          <li key={`w-${i}`} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm">
            <Badge tone="warning">Parser</Badge>
            <span className="min-w-0 flex-1 text-fg">{w}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export interface AiReparseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sourceName: string
  configured: boolean
  consentGiven: boolean
  pending: boolean
  onConfirm: () => void
}

/** Explicit consent before the subject text is sent to the Claude API. */
export function AiReparseDialog({ open, onOpenChange, sourceName, configured, consentGiven, pending, onConfirm }: AiReparseDialogProps) {
  const [agree, setAgree] = useState(consentGiven)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-warning" aria-hidden /> Re-parse with AI
          </DialogTitle>
          <DialogDescription>Claude reads the subject and proposes a richer contract.</DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-3 text-sm text-fg-muted">
          <p>
            The extracted text of <span className="font-medium text-fg">{sourceName}</span> will be sent to the Claude API
            (Anthropic). Your project code is never sent.
          </p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Items not found verbatim in the subject are marked “AI-extracted” and lower the confidence until you review them.</li>
            <li>The AI never decides pass/fail: every check stays deterministic.</li>
            <li>Manual edits made to this contract will be replaced.</li>
          </ul>
          {!configured ? (
            <p className="rounded-lg border border-warning/25 bg-warning/8 px-3 py-2 text-fg">
              No Anthropic API key is configured.{' '}
              <Link to="/settings" className="font-medium text-accent-fg underline-offset-4 hover:underline">
                Add one in Settings
              </Link>
              .
            </p>
          ) : (
            <label className="flex items-start gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-fg">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 accent-accent" />
              <span>I agree to send the subject text to the Claude API{consentGiven ? '' : ' (this also enables the consent in Settings)'}.</span>
            </label>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!configured || !agree} loading={pending} onClick={onConfirm}>
            <Sparkles aria-hidden /> Send and re-parse
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
