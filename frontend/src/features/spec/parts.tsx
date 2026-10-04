/** Small building blocks shared by the spec review tabs and the exercise editor. */
import { AlertTriangle, CircleX, Plus, X } from 'lucide-react'
import { useId, useState, type KeyboardEvent, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'
import { trailingSpaceStart, type DraftIssue } from './spec-utils'

/** Renders text with its trailing spaces shown as ␠ (prompts like "Pilot name: " must keep them). */
export function VisibleSpaces({ text, className }: { text: string; className?: string }) {
  const cut = trailingSpaceStart(text)
  const trailing = text.length - cut
  return (
    <span className={cn('font-mono whitespace-pre', className)}>
      {text.slice(0, cut)}
      {trailing > 0 && (
        <span
          className="rounded-[3px] bg-warning/12 text-warning"
          title={`${trailing} trailing space${trailing > 1 ? 's' : ''}`}
        >
          {'␠'.repeat(trailing)}
          <span className="sr-only"> ({trailing} trailing space{trailing > 1 ? 's' : ''})</span>
        </span>
      )}
    </span>
  )
}

export function FieldLabel({ htmlFor, children, hint }: { htmlFor?: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 flex items-baseline justify-between gap-2 text-xs font-medium text-fg-muted">
      <span>{children}</span>
      {hint && <span className="text-2xs font-normal text-fg-subtle">{hint}</span>}
    </label>
  )
}

export function TextArea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full min-w-0 resize-y rounded-lg border border-border-strong bg-bg-subtle px-3 py-2 font-mono text-[0.8125rem] leading-5 text-fg',
        'placeholder:text-fg-subtle focus-visible:border-accent focus-visible:outline-none',
        'focus-visible:shadow-[0_0_0_3px_color-mix(in_oklab,var(--pm-accent)_25%,transparent)]',
        className,
      )}
      {...props}
    />
  )
}

export function SectionTitle({ children, action, className }: { children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('mb-2 flex items-center justify-between gap-2', className)}>
      <h4 className="text-2xs font-semibold tracking-wider text-fg-subtle uppercase">{children}</h4>
      {action}
    </div>
  )
}

/** List of validation problems (client-side or server 422). */
export function IssueList({ issues, title, className }: { issues: DraftIssue[]; title?: string; className?: string }) {
  if (!issues.length) return null
  return (
    <div role="alert" className={cn('rounded-lg border border-fail/30 bg-fail/8 px-3.5 py-3', className)}>
      <p className="flex items-center gap-2 text-sm font-medium text-fail">
        <CircleX className="size-4 shrink-0" aria-hidden />
        {title ?? `${issues.length} problem${issues.length > 1 ? 's' : ''} to fix`}
      </p>
      <ul className="mt-2 space-y-1 text-xs text-fg-muted">
        {issues.map((issue, i) => (
          <li key={`${issue.path}-${i}`} className="flex gap-2">
            <code className="shrink-0 font-mono text-fg-subtle">{issue.path}</code>
            <span className="min-w-0 text-fg">{issue.message}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function InlineWarning({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn('flex items-start gap-2 rounded-lg border border-warning/25 bg-warning/8 px-3 py-2 text-xs text-fg', className)}>
      <AlertTriangle className="mt-px size-3.5 shrink-0 text-warning" aria-hidden />
      <span className="min-w-0">{children}</span>
    </p>
  )
}

export interface ChipInputProps {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  placeholder?: string
  tone?: 'neutral' | 'pass' | 'fail' | 'accent'
  /** Normalizes a typed value (e.g. strips "()" from builtin names). Return "" to reject. */
  normalize?: (raw: string) => string
  disabled?: boolean
  readOnly?: boolean
}

const CHIP_TONE: Record<NonNullable<ChipInputProps['tone']>, string> = {
  neutral: 'border-border-strong bg-surface-2 text-fg',
  pass: 'border-pass/25 bg-pass/10 text-pass',
  fail: 'border-fail/25 bg-fail/10 text-fail',
  accent: 'border-accent-fg/30 bg-accent/12 text-accent-fg',
}

/** Editable list of short tokens (builtins, modules, patterns): Enter / comma adds, Backspace removes. */
export function ChipInput({ label, values, onChange, placeholder, tone = 'neutral', normalize, disabled, readOnly }: ChipInputProps) {
  const [draft, setDraft] = useState('')
  const id = useId()

  const commit = (raw: string) => {
    const tokens = raw
      .split(/[,\s]+/)
      .map((t) => (normalize ? normalize(t) : t.trim()))
      .filter(Boolean)
    const next = [...values]
    for (const token of tokens) if (!next.includes(token)) next.push(token)
    if (next.length !== values.length) onChange(next)
    setDraft('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      if (draft.trim()) commit(draft)
    } else if (event.key === 'Backspace' && !draft && values.length) {
      onChange(values.slice(0, -1))
    }
  }

  return (
    <div>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <div
        className={cn(
          'flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-border-strong bg-bg-subtle px-2 py-1.5',
          'focus-within:border-accent',
          disabled && 'opacity-50',
        )}
      >
        {values.map((value) => (
          <span
            key={value}
            className={cn('inline-flex h-6 items-center gap-1 rounded-md border pr-1 pl-2 font-mono text-xs', CHIP_TONE[tone])}
          >
            {value}
            {!readOnly && (
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(values.filter((v) => v !== value))}
                className="inline-flex size-4 items-center justify-center rounded-sm opacity-70 hover:bg-fg/10 hover:opacity-100"
                aria-label={`Remove ${value} from ${label}`}
                title={`Remove ${value}`}
              >
                <X className="size-3" aria-hidden />
              </button>
            )}
          </span>
        ))}
        {!readOnly && (
          <span className="flex min-w-24 flex-1 items-center gap-1">
            <input
              id={id}
              value={draft}
              disabled={disabled}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              onBlur={() => draft.trim() && commit(draft)}
              placeholder={values.length ? '' : placeholder}
              className="h-6 min-w-0 flex-1 bg-transparent font-mono text-xs text-fg outline-none placeholder:font-sans placeholder:text-fg-subtle"
            />
            {draft.trim() && (
              <button
                type="button"
                onClick={() => commit(draft)}
                className="inline-flex size-5 items-center justify-center rounded text-fg-muted hover:bg-surface-3 hover:text-fg"
                aria-label={`Add to ${label}`}
                title="Add (Enter)"
              >
                <Plus className="size-3.5" aria-hidden />
              </button>
            )}
          </span>
        )}
        {readOnly && !values.length && <span className="text-xs text-fg-subtle">{placeholder ?? 'None'}</span>}
      </div>
    </div>
  )
}
