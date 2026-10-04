/** Presentation metadata and wording shared by the results components (no React components here). */
import {
  File,
  FileCheck2,
  FileCode2,
  FileJson,
  FilePlus2,
  FileText,
  FileWarning,
  FileX2,
  MoveRight,
  type LucideIcon,
} from 'lucide-react'
import type { ExerciseScore, ExerciseScoreStatus, ExportFormat, ScoreSummary, TreeEntryStatus } from '@/lib/types'

// ---- export ---------------------------------------------------------------------------------

export const EXPORT_FORMATS: Array<{ format: ExportFormat; label: string; hint: string; icon: LucideIcon }> = [
  { format: 'json', label: 'JSON', hint: 'Full machine-readable report', icon: FileJson },
  { format: 'md', label: 'Markdown', hint: 'For a README or an issue', icon: FileText },
  { format: 'html', label: 'HTML', hint: 'Standalone, printable', icon: FileCode2 },
]

// ---- verdict --------------------------------------------------------------------------------

const HIDDEN_TESTS_NOTE = 'Hidden grader tests may still exist.'

export function verdictCopy(score: ScoreSummary): { title: string; message: string } {
  if (score.verdict === 'ready') {
    const base = score.verdict_message?.trim() || 'All requirements that could be verified from the subject passed.'
    return {
      title: 'READY TO SUBMIT',
      message: base.includes(HIDDEN_TESTS_NOTE) ? base : `${base} ${HIDDEN_TESTS_NOTE}`,
    }
  }
  const n = score.mandatory_failures
  return {
    title: 'DO NOT SUBMIT YET',
    message:
      n > 0
        ? `${n} mandatory ${n === 1 ? 'failure remains' : 'failures remain'}.`
        : score.verdict_message?.trim() || 'Some mandatory requirements are not met.',
  }
}

// ---- exercises ------------------------------------------------------------------------------

export type ExerciseTone = 'pass' | 'fail' | 'warning' | 'bonus' | 'neutral'

export const EXERCISE_STATUS: Record<ExerciseScoreStatus, { label: string; tone: ExerciseTone }> = {
  pass: { label: 'Pass', tone: 'pass' },
  fail: { label: 'Fail', tone: 'fail' },
  warning: { label: 'Warning', tone: 'warning' },
  missing: { label: 'Missing', tone: 'fail' },
  not_implemented: { label: 'Not implemented', tone: 'neutral' },
  partial: { label: 'Partial', tone: 'warning' },
}

export function exerciseStatusMeta(ex: ExerciseScore): { label: string; tone: ExerciseTone } {
  const meta = EXERCISE_STATUS[ex.status]
  // A failing bonus never blocks: show it in the bonus color, not as a red failure.
  if (ex.bonus && meta.tone === 'fail') return { ...meta, tone: 'bonus' }
  return meta
}

// ---- history --------------------------------------------------------------------------------

export function formatDelta(delta: number): string {
  const rounded = Math.round(delta * 10) / 10
  if (rounded === 0) return '±0 pts'
  return `${rounded > 0 ? '+' : '−'}${Math.abs(rounded).toFixed(1)} pts`
}

// ---- files ----------------------------------------------------------------------------------

export const TREE_STATUS_META: Record<TreeEntryStatus, { label: string; icon: LucideIcon; className: string; hint: string }> = {
  expected: { label: 'Expected', icon: FileCheck2, className: 'text-pass', hint: 'Required by the subject and present' },
  ok: { label: 'OK', icon: File, className: 'text-fg-muted', hint: 'Present' },
  missing: { label: 'Missing', icon: FileX2, className: 'text-fail', hint: 'Required by the subject but not found' },
  extra: { label: 'Extra', icon: FilePlus2, className: 'text-info', hint: 'Not mentioned by the subject' },
  parasite: { label: 'Parasite', icon: FileWarning, className: 'text-warning', hint: 'Must not be submitted (cache, build artifact…)' },
  misplaced: { label: 'Misplaced', icon: MoveRight, className: 'text-fail', hint: 'Wrong folder or wrong letter case' },
}
