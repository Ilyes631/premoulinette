import { Info, Server, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui'
import type { AnalysisReport } from '@/lib/types'
import { useResults } from '../shared/results-context'
import { SectionCard } from '../shared/section-card'
import { CategoryBars } from './category-bars'
import { ExercisesGrid } from './exercises-grid'
import { GitCard } from './git-card'
import { ReadinessHero, ScoreTiles } from './readiness-hero'
import { TopIssues } from './top-issues'

export function OverviewTab() {
  const { report, goToTab } = useResults()
  const { score } = report
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ReadinessHero score={score} />
        </div>
        <ScoreTiles score={score} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0 lg:col-span-2">
          <TopIssues checks={report.checks} />
        </div>
        <GitCard git={report.project.git} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0 lg:col-span-2">
          <CategoryBars categories={score.categories} />
        </div>
        <EnvironmentCard report={report} />
      </div>
      <ExercisesGrid exercises={score.exercises} onSelect={(ex) => goToTab('issues', { q: ex.file })} />
      <Disclaimer />
    </div>
  )
}

function EnvironmentCard({ report }: { report: AnalysisReport }) {
  const { sandbox, pipeline_warnings: warnings, project } = report
  const docker = sandbox.mode === 'docker'
  return (
    <SectionCard icon={Server} title="Environment" description="Where your code ran.">
      <dl className="space-y-2 text-sm">
        <Row label="Sandbox">
          <Badge tone={docker ? 'pass' : 'warning'} variant="outline">
            {docker ? 'Docker · safe mode' : 'Local · developer mode'}
          </Badge>
        </Row>
        {sandbox.python_version && <Row label="Python">{sandbox.python_version}</Row>}
        {sandbox.image && <Row label="Image"><span className="font-mono text-xs">{sandbox.image}</span></Row>}
        <Row label="Network">{sandbox.network ? 'Allowed' : 'Disabled'}</Row>
        <Row label="Files">
          {project.file_count} · {project.python_files} Python
        </Row>
        {project.detected_root && (
          <Row label="Root">
            <span className="font-mono text-xs">{project.detected_root}</span>
          </Row>
        )}
      </dl>
      {(sandbox.warnings.length > 0 || warnings.length > 0 || project.root_note) && (
        <ul className="mt-3 space-y-1.5 border-t border-border pt-3 text-xs text-warning">
          {project.root_note && (
            <li className="flex gap-1.5 text-fg-muted">
              <Info className="mt-px size-3.5 shrink-0" aria-hidden />
              {project.root_note}
            </li>
          )}
          {[...sandbox.warnings, ...warnings].map((w) => (
            <li key={w} className="flex gap-1.5">
              <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
              {w}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-fg">{children}</dd>
    </div>
  )
}

export function Disclaimer() {
  return (
    <p className="flex items-start gap-2 rounded-lg border border-border px-4 py-3 text-xs text-pretty text-fg-muted">
      <Info className="mt-px size-3.5 shrink-0 text-fg-subtle" aria-hidden />
      <span>
        PréMoulinette is a local pre-check, not the official grader. It only verifies what can be read in the subject:
        the real moulinette may run hidden tests, and this score is not a grade.
      </span>
    </p>
  )
}
