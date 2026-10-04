import { ArrowLeft, ArrowRight, FileQuestion, RotateCw, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button, buttonVariants, EmptyState, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger, Tooltip } from '@/components/ui'
import { ConstraintsTab } from '@/features/spec/constraints-tab'
import { ExerciseEditor } from '@/features/spec/exercise-editor'
import { JsonTab } from '@/features/spec/json-tab'
import { IssueList } from '@/features/spec/parts'
import { RequirementsTab } from '@/features/spec/requirements-tab'
import { readSelection, selectSubject } from '@/features/spec/selection'
import { SourceTab } from '@/features/spec/source-tab'
import { AiReparseDialog, SpecHeader, SpecStatsGrid, ValidationPanel } from '@/features/spec/spec-header'
import { appendExercise, collectTestIds, newExercise, removeExercise, replaceExercise } from '@/features/spec/spec-utils'
import { StructureTab } from '@/features/spec/structure-tab'
import { TestsTab } from '@/features/spec/tests-tab'
import { useSpecSaver } from '@/features/spec/use-spec-saver'
import { errorMessage, isApiError } from '@/lib/api'
import { toastDemoReadOnly } from '@/lib/demo/notify'
import { useHealth, useReparseSubject, useSettings, useStartAnalysis, useSubject, useUpdateSettings } from '@/lib/queries'
import { toast } from '@/lib/toast'
import type { ExerciseSpec, PracticalSpec, SubjectView } from '@/lib/types'

type TabKey = 'requirements' | 'tests' | 'constraints' | 'structure' | 'json' | 'source'
const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'requirements', label: 'Requirements' },
  { key: 'tests', label: 'Tests' },
  { key: 'constraints', label: 'Constraints' },
  { key: 'structure', label: 'Structure' },
  { key: 'json', label: 'JSON' },
  { key: 'source', label: 'Source' },
]

/** Editor state: which exercise is open (index null = a new exercise). */
interface EditorState {
  index: number | null
  draft: ExerciseSpec
}

export function SpecReviewPage() {
  const { id = '' } = useParams<{ id: string }>()
  const query = useSubject(id)

  if (query.isPending) return <SpecReviewSkeleton />
  if (query.isError) {
    const notFound = isApiError(query.error) && query.error.status === 404
    return (
      <EmptyState
        icon={FileQuestion}
        tone={notFound ? 'neutral' : 'fail'}
        title={notFound ? 'This subject does not exist' : 'The subject could not be loaded'}
        description={notFound ? 'It may have been imported in another data folder. Import it again from the home page.' : errorMessage(query.error)}
      >
        {!notFound && (
          <Button onClick={() => void query.refetch()}>
            <RotateCw aria-hidden /> Retry
          </Button>
        )}
        <Link to="/" className={buttonVariants({ variant: notFound ? 'primary' : 'ghost' })}>
          Back to home
        </Link>
      </EmptyState>
    )
  }
  return <SpecReview subject={query.data} />
}

function SpecReviewSkeleton() {
  return (
    <div className="space-y-6" aria-busy aria-label="Loading the subject">
      <div className="space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-5 w-1/2" />
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
      <Skeleton className="h-9 w-96 max-w-full" />
      <Skeleton className="h-64" />
    </div>
  )
}

function SpecReview({ subject }: { subject: SubjectView }) {
  const navigate = useNavigate()
  const health = useHealth()
  const settings = useSettings()
  const updateSettings = useUpdateSettings()
  const reparse = useReparseSubject(subject.id)
  const startAnalysis = useStartAnalysis()
  const saver = useSpecSaver(subject.id)
  const [tab, setTab] = useState<TabKey>('requirements')
  const [editor, setEditor] = useState<EditorState | null>(null)
  const [aiOpen, setAiOpen] = useState(false)

  const spec = subject.spec
  const projectId = readSelection().projectId
  const errors = subject.validation.filter((i) => i.level === 'error').length
  const aiEnabled = health.data?.ai.enabled === true

  const openExercise = (index: number) => {
    const exercise = spec.exercises[index]
    if (!exercise) return
    saver.clearErrors()
    setEditor({ index, draft: exercise })
  }
  const addExercise = () => {
    saver.clearErrors()
    setEditor({ index: null, draft: newExercise(new Set(spec.exercises.map((e) => e.id))) })
  }

  const editorIds = useMemo(() => {
    if (!editor) return { exercises: new Set<string>(), tests: new Set<string>() }
    const exercises = new Set(spec.exercises.filter((_, i) => i !== editor.index).map((e) => e.id))
    return { exercises, tests: collectTestIds(spec, editor.index ?? undefined) }
  }, [editor, spec])

  const save = (next: PracticalSpec, title?: string) => saver.save(next, title)

  const saveExercise = (exercise: ExerciseSpec) => {
    if (!editor) return Promise.resolve(false)
    const next = editor.index === null ? appendExercise(spec, exercise) : replaceExercise(spec, editor.index, exercise)
    return save(next, editor.index === null ? 'Exercise added' : 'Exercise saved')
  }
  const deleteExercise = () => {
    if (!editor || editor.index === null) return Promise.resolve(false)
    return save(removeExercise(spec, editor.index), 'Exercise deleted')
  }

  const analyze = async () => {
    selectSubject(subject.id)
    if (!projectId) {
      navigate('/')
      return
    }
    try {
      const { job_id } = await startAnalysis.mutateAsync({ subject_id: subject.id, project_id: projectId })
      navigate(`/jobs/${job_id}`)
    } catch (error) {
      toast({ title: 'The analysis could not start', description: errorMessage(error), tone: 'error' })
      navigate('/')
    }
  }

  const confirmAiReparse = async () => {
    try {
      if (settings.data && !settings.data.ai_consent_subject) await updateSettings.mutateAsync({ ai_consent_subject: true })
      await reparse.mutateAsync(true)
      setAiOpen(false)
      toast({ title: 'Subject re-parsed with AI', description: 'Review the AI-extracted items before analyzing.', tone: 'success' })
    } catch (error) {
      if (toastDemoReadOnly(error)) return setAiOpen(false)
      toast({ title: 'AI re-parse failed', description: errorMessage(error), tone: 'error' })
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1.5 rounded-md text-xs text-fg-muted transition-colors hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Home
      </Link>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <SpecHeader subject={subject} />
        <div className="flex shrink-0 flex-col items-stretch gap-2 sm:flex-row sm:items-center lg:flex-col lg:items-end">
          <div className="flex flex-wrap gap-2">
            {aiEnabled && (
              <Button variant="outline" onClick={() => setAiOpen(true)}>
                <Sparkles aria-hidden /> Re-parse with AI
              </Button>
            )}
            <Tooltip content={errors ? `${errors} validation error${errors > 1 ? 's' : ''}: the analysis may be inaccurate` : undefined}>
              <Button variant="primary" size="lg" onClick={analyze} loading={startAnalysis.isPending}>
                Use this contract <ArrowRight aria-hidden /> Analyze
              </Button>
            </Tooltip>
          </div>
          <p className="text-xs text-fg-subtle lg:text-right">
            {projectId ? 'Starts the analysis of the selected project.' : 'Then choose the project to analyze.'}
          </p>
        </div>
      </div>

      <SpecStatsGrid subject={subject} />

      <ValidationPanel issues={subject.validation} warnings={subject.warnings} onOpenExercise={openExercise} />

      <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)} className="space-y-4">
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <TabsList variant="underline" aria-label="Contract sections" className="min-w-max">
            {TABS.map((t) => (
              <TabsTrigger key={t.key} value={t.key}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        {!editor && tab !== 'json' && <IssueList issues={saver.errors} title="The server rejected the contract" />}
        <TabsContent value="requirements">
          <RequirementsTab exercises={spec.exercises} onEdit={openExercise} onAdd={addExercise} />
        </TabsContent>
        <TabsContent value="tests">
          <TestsTab subjectId={subject.id} />
        </TabsContent>
        <TabsContent value="constraints">
          <ConstraintsTab spec={spec} saving={saver.saving} onSave={(s) => save(s, 'Constraints saved')} onEditExercise={openExercise} />
        </TabsContent>
        <TabsContent value="structure">
          <StructureTab spec={spec} saving={saver.saving} onSave={(s) => save(s, 'Structure saved')} />
        </TabsContent>
        <TabsContent value="json">
          <JsonTab
            spec={spec}
            fileName={`${(subject.source_name || 'subject').replace(/\.[^.]+$/, '')}.spec.json`}
            saving={saver.saving}
            serverErrors={editor ? [] : saver.errors}
            onSave={(s) => save(s, 'Contract saved')}
          />
        </TabsContent>
        <TabsContent value="source">
          <SourceTab subjectId={subject.id} sourceName={subject.source_name} />
        </TabsContent>
      </Tabs>

      {editor && (
        <ExerciseEditor
          open
          onOpenChange={(open) => !open && setEditor(null)}
          original={editor.index === null ? null : (spec.exercises[editor.index] ?? null)}
          initial={editor.draft}
          otherExerciseIds={editorIds.exercises}
          otherTestIds={editorIds.tests}
          onSave={saveExercise}
          onDelete={editor.index === null ? undefined : deleteExercise}
          saving={saver.saving}
          serverErrors={saver.errors}
        />
      )}

      {aiOpen && (
        <AiReparseDialog
          open
          onOpenChange={setAiOpen}
          sourceName={subject.source_name}
          configured={health.data?.ai.configured === true}
          consentGiven={settings.data?.ai_consent_subject === true}
          pending={reparse.isPending || updateSettings.isPending}
          onConfirm={() => void confirmAiReparse()}
        />
      )}
    </div>
  )
}
