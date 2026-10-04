/**
 * Builds the sections of the "Report" tab from the AnalysisReport. Same section list as the
 * backend Markdown/HTML export (report/export.py): Repository, Subject, Mandatory requirements, Optional
 * requirements, Structure, Functions, Scripts, Constraints, Static analysis, Runtime analysis, Known tests,
 * Derived tests, Warnings, Bonus.
 */
import { compareChecks } from '@/lib/check-meta'
import { formatPercent } from '@/lib/format'
import type { AnalysisReport, CheckResult, ExerciseScore } from '@/lib/types'

export type SectionTone = 'pass' | 'fail' | 'warning' | 'bonus' | 'neutral'

export interface ReportFact {
  label: string
  value: string
}

export interface ReportSection {
  id: string
  title: string
  summary: string
  tone: SectionTone
  facts: ReportFact[]
  exercises: ExerciseScore[]
  checks: CheckResult[]
  notes: string[]
  empty: string
}

function section(partial: Partial<ReportSection> & Pick<ReportSection, 'id' | 'title'>): ReportSection {
  return { summary: '', tone: 'neutral', facts: [], exercises: [], checks: [], notes: [], empty: 'Nothing to report.', ...partial }
}

function checkSummary(checks: CheckResult[]): { summary: string; tone: SectionTone } {
  if (checks.length === 0) return { summary: 'No checks', tone: 'neutral' }
  const passed = checks.filter((c) => c.status === 'pass').length
  const failing = checks.filter((c) => c.status === 'fail' || c.status === 'skipped').length
  const warnings = checks.filter((c) => c.status === 'warning').length
  const bonus = checks.filter((c) => c.status === 'bonus').length
  const parts = [`${passed} / ${checks.length} passed`]
  if (failing) parts.push(`${failing} failing`)
  if (warnings) parts.push(`${warnings} ${warnings === 1 ? 'warning' : 'warnings'}`)
  if (bonus) parts.push(`${bonus} bonus not done`)
  const blocking = checks.some((c) => (c.status === 'fail' || c.status === 'skipped') && c.mandatory && !c.bonus)
  const tone: SectionTone = blocking ? 'fail' : failing || warnings ? 'warning' : bonus ? 'bonus' : 'pass'
  return { summary: parts.join(' · '), tone }
}

function checkSection(id: string, title: string, checks: CheckResult[], empty: string): ReportSection {
  return section({ id, title, checks: [...checks].sort(compareChecks), ...checkSummary(checks), empty })
}

function withNotes(base: ReportSection, notes: string[]): ReportSection {
  if (notes.length === 0) return base
  const label = `${notes.length} ${notes.length === 1 ? 'note' : 'notes'}`
  return {
    ...base,
    notes,
    summary: base.checks.length ? `${base.summary} · ${label}` : label,
    tone: base.tone === 'fail' ? 'fail' : 'warning',
  }
}

function exerciseSummary(exercises: ExerciseScore[], bonus: boolean): { summary: string; tone: SectionTone } {
  if (exercises.length === 0) return { summary: bonus ? 'No bonus' : 'No exercise', tone: 'neutral' }
  const done = exercises.filter((e) => e.status === 'pass').length
  const tone: SectionTone = done === exercises.length ? 'pass' : bonus ? 'bonus' : 'fail'
  return { summary: `${done} / ${exercises.length} complete`, tone }
}

function list(values: string[] | null | undefined, none = 'none'): string {
  if (values === null || values === undefined) return 'any'
  return values.length ? values.join(', ') : none
}

export function buildReportSections(report: AnalysisReport): ReportSection[] {
  const { checks, project, spec, score, sandbox } = report
  const git = project.git
  const byCategory = (cat: CheckResult['category']) => checks.filter((c) => c.category === cat)
  const scriptExercises = new Set(spec.exercises.filter((e) => e.kind === 'script').map((e) => e.id))
  const isScriptCheck = (c: CheckResult) =>
    c.id.startsWith('prompt:') ||
    c.category === 'output' ||
    (c.category === 'explicit_tests' && c.exercise_id !== null && scriptExercises.has(c.exercise_id))
  const mandatoryExercises = score.exercises.filter((e) => !e.bonus)
  const bonusExercises = score.exercises.filter((e) => e.bonus)
  const constraints = spec.global_constraints

  const repoFacts: ReportFact[] = [
    { label: 'Project', value: project.name },
    { label: 'Source', value: project.path ? `${project.source_kind} · ${project.path}` : project.source_kind },
    { label: 'Detected root', value: project.detected_root || '(top folder)' },
    { label: 'Files', value: `${project.file_count} (${project.python_files} Python)` },
    {
      label: 'Sandbox',
      value: `${sandbox.mode === 'docker' ? 'Docker (safe mode)' : 'Local (developer mode)'}${
        sandbox.python_version ? ` · Python ${sandbox.python_version}` : ''
      }`,
    },
  ]
  if (git?.is_repo) {
    repoFacts.push(
      { label: 'Branch', value: git.branch ?? 'detached HEAD' },
      { label: 'Last commit', value: [git.head?.slice(0, 7), git.last_commit_message].filter(Boolean).join(' ') || '—' },
      { label: 'Working tree', value: git.dirty ? 'uncommitted changes' : 'clean' },
      { label: 'Untracked files', value: String(git.untracked.length) },
    )
  } else {
    repoFacts.push({ label: 'Git', value: git ? 'not a Git repository' : 'unavailable' })
  }
  const gitChecks = byCategory('git')

  return [
    section({
      id: 'repository',
      title: 'Repository',
      facts: repoFacts,
      checks: [...gitChecks].sort(compareChecks),
      ...(gitChecks.length ? checkSummary(gitChecks) : { summary: project.name, tone: 'neutral' as const }),
      notes: project.root_note ? [project.root_note] : [],
    }),
    section({
      id: 'subject',
      title: 'Subject',
      summary: `${mandatoryExercises.length} mandatory · ${bonusExercises.length} bonus exercises`,
      facts: [
        { label: 'Title', value: report.subject.title },
        { label: 'Source', value: report.subject.source_name ?? '—' },
        { label: 'Parser', value: report.subject.parser },
        { label: 'Language', value: `${spec.language}${spec.language_version ? ` ${spec.language_version}` : ''}` },
        { label: 'Reviewed', value: spec.metadata.reviewed_by_user ? 'yes' : 'no (as extracted)' },
        { label: 'Allowed builtins', value: list(constraints.allowed_builtins) },
        { label: 'Forbidden builtins', value: list(constraints.forbidden_builtins) },
        { label: 'Allowed imports', value: list(constraints.allowed_imports, 'none (no import allowed)') },
      ],
      notes: spec.notes,
    }),
    section({
      id: 'mandatory',
      title: 'Mandatory requirements',
      exercises: mandatoryExercises,
      ...exerciseSummary(mandatoryExercises, false),
      facts: [
        { label: 'Mandatory readiness', value: formatPercent(score.mandatory_readiness, 1) },
        { label: 'Mandatory checks', value: `${score.mandatory_passed} / ${score.mandatory_total} passed` },
      ],
    }),
    section({
      id: 'optional',
      title: 'Optional requirements',
      exercises: bonusExercises,
      ...exerciseSummary(bonusExercises, true),
      empty: 'The subject defines no optional exercise.',
    }),
    checkSection('structure', 'Structure', byCategory('structure'), 'No structure requirement.'),
    checkSection('functions', 'Functions', byCategory('functions'), 'No function requirement.'),
    checkSection('scripts', 'Scripts', checks.filter(isScriptCheck), 'No script exercise.'),
    checkSection('constraints', 'Constraints', byCategory('constraints'), 'No constraint was violated or checked.'),
    checkSection('static', 'Static analysis', byCategory('syntax'), 'No Python file was compiled.'),
    checkSection('runtime', 'Runtime analysis', byCategory('runtime'), 'No import-time behavior was checked.'),
    checkSection(
      'known-tests',
      'Known tests',
      checks.filter((c) => c.category === 'explicit_tests' && !isScriptCheck(c)),
      'The subject gives no function example.',
    ),
    checkSection('derived-tests', 'Derived tests', byCategory('derived_tests'), 'No rule could be turned into a test.'),
    withNotes(
      checkSection('warnings', 'Warnings', checks.filter((c) => c.status === 'warning'), 'No warning.'),
      [...report.pipeline_warnings, ...sandbox.warnings],
    ),
    checkSection('bonus', 'Bonus', checks.filter((c) => c.bonus || c.status === 'bonus'), 'No bonus check.'),
  ]
}
