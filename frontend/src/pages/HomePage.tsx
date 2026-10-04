import { FileSearch, FlaskConical, ShieldCheck, Sparkles, Wrench } from 'lucide-react'
import { motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui'
import { AnalyzeBar } from '@/features/home/analyze-bar'
import type { ImportState } from '@/features/home/import-card'
import { analyzeBlocker } from '@/features/home/logic'
import { ProjectCard } from '@/features/home/project-card'
import { RecentAnalyses } from '@/features/home/recent-analyses'
import { SandboxBanner } from '@/features/home/sandbox-banner'
import { SELECTED_PROJECT_KEY, SELECTED_SUBJECT_KEY, useStoredId } from '@/features/home/selection'
import { SubjectCard } from '@/features/home/subject-card'
import { rememberJob } from '@/features/progress/job-context'
import { errorMessage } from '@/lib/api'
import { describeSandbox } from '@/app/sandbox-status'
import { useHealth, useLoadDemo, useProject, useStartAnalysis, useSubject } from '@/lib/queries'
import { toast } from '@/lib/toast'
import type { DemoVariant } from '@/lib/types'

const VALUE_PROPS = [
  {
    icon: FileSearch,
    title: 'Reads the subject',
    text: 'Files, signatures, examples and constraints become an exact, reviewable contract.',
  },
  {
    icon: ShieldCheck,
    title: 'Runs your code safely',
    text: 'Sandboxed tests, byte-exact output diffs, forbidden builtins and git checks.',
  },
  {
    icon: Wrench,
    title: 'Explains every failure',
    text: 'Deterministic diagnosis, where it happens, and the minimal fix.',
  },
] as const

const ENTER_TRANSITION = { duration: 0.32, ease: [0.25, 1, 0.5, 1] as const }

export function HomePage() {
  const navigate = useNavigate()
  const [subjectId, setSubjectId] = useStoredId(SELECTED_SUBJECT_KEY)
  const [projectId, setProjectId] = useStoredId(SELECTED_PROJECT_KEY)
  const [subjectState, setSubjectState] = useState<ImportState>('empty')
  const [projectState, setProjectState] = useState<ImportState>('empty')
  const [startError, setStartError] = useState<string | null>(null)

  const subject = useSubject(subjectId)
  const project = useProject(projectId)
  const demo = useLoadDemo()
  const start = useStartAnalysis()
  const health = useHealth()
  const sandbox = describeSandbox(health.data, { loading: health.isPending, error: health.isError })

  const loadDemo = (variant: DemoVariant) => {
    setStartError(null)
    demo.mutate(variant, {
      onSuccess: ({ subject: s, project: p }) => {
        setSubjectId(s.id)
        setProjectId(p.id)
        toast({
          title: variant === 'buggy' ? 'Demo project loaded' : 'Fixed demo loaded',
          description: `${s.title} · ${p.name}`,
          tone: 'success',
        })
      },
      onError: (err) => toast({ title: 'Could not load the demo', description: errorMessage(err), tone: 'error' }),
    })
  }

  const ready = analyzeBlocker(subjectState, projectState) === null && Boolean(subjectId && projectId)

  const analyze = useCallback(() => {
    if (!ready || !subjectId || !projectId || start.isPending) return
    setStartError(null)
    start.mutate(
      { subject_id: subjectId, project_id: projectId },
      {
        onSuccess: ({ job_id }) => {
          rememberJob(job_id, {
            subject_id: subjectId,
            project_id: projectId,
            subject_title: subject.data?.title ?? null,
            project_name: project.data?.name ?? null,
          })
          navigate(`/jobs/${encodeURIComponent(job_id)}`)
        },
        onError: (err) => setStartError(`Could not start the analysis: ${errorMessage(err)}`),
      },
    )
  }, [ready, subjectId, projectId, start, subject.data, project.data, navigate])

  // Keyboard: Ctrl/Cmd+Enter anywhere, plain Enter when nothing is focused.
  const analyzeRef = useRef(analyze)
  useEffect(() => {
    analyzeRef.current = analyze
  }, [analyze])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Enter' || e.defaultPrevented || e.isComposing || e.altKey || e.shiftKey) return
      const withModifier = e.ctrlKey || e.metaKey
      const target = e.target instanceof HTMLElement ? e.target : null
      const nothingFocused = !target || target === document.body || target.id === 'main-content'
      if (!withModifier && !nothingFocused) return
      e.preventDefault()
      analyzeRef.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const demoBusy = demo.isPending

  return (
    <div className="flex flex-col gap-10 sm:gap-12">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={ENTER_TRANSITION}
        aria-labelledby="home-title"
        className="flex flex-col gap-8 pt-2 sm:pt-6"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-border-strong bg-surface/70 px-2.5 py-1 text-xs font-medium text-fg-muted shadow-card backdrop-blur">
              <FlaskConical className="size-3.5 text-accent-fg" aria-hidden />
              Local pre-grader for Python assignments
            </p>
            <h1
              id="home-title"
              className="bg-gradient-to-b from-fg to-fg/65 bg-clip-text text-4xl font-semibold tracking-[-0.035em] text-transparent sm:text-5xl"
            >
              PréMoulinette
            </h1>
            <p className="mt-3 text-base text-pretty text-fg-muted sm:text-lg">
              Test your project before the real submission.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" onClick={() => loadDemo('buggy')} loading={demoBusy && demo.variables === 'buggy'} disabled={demoBusy}>
              {!(demoBusy && demo.variables === 'buggy') && <Sparkles aria-hidden />}
              Load demo project
            </Button>
            <Button variant="link" size="sm" onClick={() => loadDemo('fixed')} disabled={demoBusy} className="text-xs">
              Load fixed demo
            </Button>
          </div>
        </div>

        <ul className="grid gap-3 sm:grid-cols-3">
          {VALUE_PROPS.map(({ icon: Icon, title, text }) => (
            <li key={title} className="flex gap-3 rounded-xl border border-border bg-surface/60 p-4 backdrop-blur-sm">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-accent/25 bg-accent/10 text-accent-fg">
                <Icon className="size-4" aria-hidden />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg">{title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-fg-muted">{text}</p>
              </div>
            </li>
          ))}
        </ul>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...ENTER_TRANSITION, delay: 0.06 }}
        aria-label="Import"
        className="flex flex-col gap-4"
      >
        <SandboxBanner />
        <div className="grid items-stretch gap-4 lg:grid-cols-2">
          <SubjectCard
            subjectId={subjectId}
            onSelect={setSubjectId}
            externalBusy={demoBusy}
            onStateChange={setSubjectState}
          />
          <ProjectCard
            projectId={projectId}
            onSelect={setProjectId}
            externalBusy={demoBusy}
            onStateChange={setProjectState}
          />
        </div>
        <AnalyzeBar
          subjectState={subjectState}
          projectState={projectState}
          subjectLabel={subject.data?.title}
          projectLabel={project.data?.name}
          starting={start.isPending}
          error={startError}
          sandboxWarning={
            sandbox.kind === 'none'
              ? 'No sandbox is configured: the analysis cannot run your code until you fix it in Settings.'
              : null
          }
          onAnalyze={analyze}
        />
      </motion.section>

      <RecentAnalyses />
    </div>
  )
}
