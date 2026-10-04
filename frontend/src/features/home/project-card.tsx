import {
  FileArchive,
  FileCode2,
  Files,
  FolderOpen,
  FolderTree,
  FolderUp,
  GitBranch,
  HardDrive,
  RefreshCw,
  X,
} from 'lucide-react'
import { useEffect, useId, useState, type FormEvent } from 'react'
import { DemoReadOnlyNotice } from '@/components/demo/read-only-notice'
import { Badge, Button, Input, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger, Tooltip } from '@/components/ui'
import { errorMessage, isApiError, isDemoReadOnlyError } from '@/lib/api'
import { useCreateProject, useProject, type ProjectSource } from '@/lib/queries'
import type { ProjectSourceKindView, ProjectView } from '@/lib/types'
import { isZipFile, prepareFolderFiles, ZIP_ACCEPT } from '@/lib/uploads'
import { DropArea } from './drop-area'
import { ImportCard, ImportError, type ImportState } from './import-card'
import { looksAbsolute, normalizePathInput } from './logic'
import { BusyContent, MiniStat } from './subject-card'

type SourceTab = 'path' | 'zip' | 'folder'

const SOURCE_LABEL: Record<ProjectSourceKindView, string> = {
  path: 'Local folder',
  zip: 'ZIP archive',
  upload: 'Folder upload',
  demo: 'Demo project',
}

export interface ProjectCardProps {
  projectId: string | null
  onSelect: (id: string | null) => void
  externalBusy?: boolean
  onStateChange?: (state: ImportState) => void
}

export function ProjectCard({ projectId, onSelect, externalBusy = false, onStateChange }: ProjectCardProps) {
  const project = useProject(projectId)
  const create = useCreateProject()
  const [tab, setTab] = useState<SourceTab>('path')
  const [replacing, setReplacing] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [busyLabel, setBusyLabel] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    if (project.isError && isApiError(project.error) && project.error.status === 404) onSelect(null)
  }, [project.isError, project.error, onSelect])

  const submit = (source: ProjectSource, label: string, importNote: string | null = null) => {
    setLocalError(null)
    setNote(importNote)
    setBusyLabel(label)
    create.mutate(source, {
      onSuccess: (view) => {
        onSelect(view.id)
        setReplacing(false)
      },
      onSettled: () => setBusyLabel(null),
    })
  }

  const onZip = (files: File[]) => {
    const file = files[0]
    if (!file) return
    if (!isZipFile(file)) {
      setLocalError(`"${file.name}" is not a .zip archive.`)
      return
    }
    submit({ kind: 'zip', file }, `Importing ${file.name}…`)
  }

  const onFolder = (files: File[]) => {
    const selection = prepareFolderFiles(files)
    if (selection.error) {
      setLocalError(selection.error)
      return
    }
    const skipped = selection.skipped
      ? `${selection.skipped} file${selection.skipped === 1 ? '' : 's'} from dependency folders (node_modules, .venv…) were skipped.`
      : null
    submit({ kind: 'folder', files: selection.files }, `Uploading ${selection.files.length} files…`, skipped)
  }

  const onPath = (path: string) => submit({ kind: 'path', path }, 'Copying your folder…')

  const uploading = create.isPending || externalBusy
  const data = project.data && project.data.id === projectId ? project.data : undefined
  const loading = Boolean(projectId) && project.isPending
  const showSummary = Boolean(data) && !replacing && !uploading
  const errorText = localError ?? (create.isError ? errorMessage(create.error) : null)
  // The online demo refuses imports: explained by a notice, not reported as a failure.
  const demoRefusal = !localError && isDemoReadOnlyError(create.error) ? create.error : null

  const state: ImportState = uploading
    ? 'uploading'
    : (errorText && !demoRefusal) || (project.isError && !data)
      ? 'error'
      : data
        ? 'ready'
        : loading
          ? 'loading'
          : 'empty'

  useEffect(() => {
    onStateChange?.(state)
  }, [state, onStateChange])

  return (
    <ImportCard
      step={2}
      labelId="project-card-title"
      title="Student project"
      description="Your code. It is copied into a snapshot, never modified."
      icon={FolderTree}
      state={state}
    >
      {showSummary && data ? (
        <ProjectSummary project={data} onReplace={() => setReplacing(true)} />
      ) : loading && !uploading && !replacing ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading project">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-3.5 w-3/4" />
          <div className="grid grid-cols-3 gap-2">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        </div>
      ) : uploading ? (
        <div className="flex min-h-44 flex-col items-center justify-center rounded-xl border border-dashed border-accent/40 bg-accent/[0.04] px-4 py-6 text-center">
          <BusyContent
            title={busyLabel ?? 'Loading the demo project…'}
            hint="Snapshotting files and reading git status"
          />
        </div>
      ) : (
        <Tabs value={tab} onValueChange={(v) => setTab(v as SourceTab)} className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <TabsList aria-label="Project source" className="max-w-full overflow-x-auto">
              <TabsTrigger value="path">
                <HardDrive aria-hidden />
                Local folder
              </TabsTrigger>
              <TabsTrigger value="zip">
                <FileArchive aria-hidden />
                ZIP
              </TabsTrigger>
              <TabsTrigger value="folder">
                <FolderUp aria-hidden />
                <span className="hidden min-[420px]:inline">Folder upload</span>
                <span className="min-[420px]:hidden">Upload</span>
              </TabsTrigger>
            </TabsList>
            {replacing && data && (
              <Tooltip content="Keep the current project">
                <Button size="icon-sm" variant="ghost" aria-label="Cancel replacing the project" onClick={() => setReplacing(false)}>
                  <X aria-hidden />
                </Button>
              </Tooltip>
            )}
          </div>

          <TabsContent value="path">
            <PathForm onSubmit={onPath} onInvalid={setLocalError} />
          </TabsContent>
          <TabsContent value="zip">
            <DropArea
              onFiles={onZip}
              accept={ZIP_ACCEPT}
              inputLabel="Project ZIP archive"
              icon={FileArchive}
              title="Drop project.zip here or browse"
              hint="Up to 5000 files · 50 MB"
              browseLabel="Browse ZIP"
              className="min-h-36"
            />
          </TabsContent>
          <TabsContent value="folder">
            <DropArea
              onFiles={onFolder}
              directory
              inputLabel="Project folder"
              icon={FolderUp}
              title="Pick your project folder"
              hint="Dependency folders (node_modules, .venv…) are skipped"
              browseLabel="Choose folder"
              className="min-h-36"
            />
          </TabsContent>
        </Tabs>
      )}

      {note && showSummary && <p className="mt-3 text-xs text-fg-subtle">{note}</p>}
      {demoRefusal && !uploading ? (
        <DemoReadOnlyNotice action={demoRefusal.action} className="mt-3" />
      ) : (
        errorText && !uploading && <ImportError title="The project could not be imported" message={errorText} />
      )}
      {project.isError && !data && !uploading && !(isApiError(project.error) && project.error.status === 404) && (
        <ImportError title="The selected project could not be loaded" message={errorMessage(project.error)}>
          <Button size="sm" variant="secondary" onClick={() => void project.refetch()}>
            <RefreshCw aria-hidden />
            Retry
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onSelect(null)}>
            Import another project
          </Button>
        </ImportError>
      )}
    </ImportCard>
  )
}

function PathForm({ onSubmit, onInvalid }: { onSubmit: (path: string) => void; onInvalid: (msg: string | null) => void }) {
  const inputId = useId()
  const helpId = useId()
  const [value, setValue] = useState('')
  const [invalid, setInvalid] = useState(false)

  const handle = (e: FormEvent) => {
    e.preventDefault()
    const path = normalizePathInput(value)
    if (!path) {
      setInvalid(true)
      onInvalid('Enter the absolute path of your project folder.')
      return
    }
    if (!looksAbsolute(path)) {
      setInvalid(true)
      onInvalid(`"${path}" is not an absolute path (e.g. C:\\Users\\me\\tp1 or /home/me/tp1).`)
      return
    }
    setInvalid(false)
    onInvalid(null)
    onSubmit(path)
  }

  return (
    <form onSubmit={handle} className="flex flex-col gap-2.5 rounded-xl border border-border bg-bg-subtle/60 p-3.5">
      <label htmlFor={inputId} className="text-xs font-medium text-fg-muted">
        Absolute path of your project folder
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id={inputId}
          value={value}
          invalid={invalid}
          onChange={(e) => {
            setValue(e.target.value)
            if (invalid) setInvalid(false)
          }}
          placeholder="C:\Users\me\epita\tp1"
          spellCheck={false}
          autoComplete="off"
          aria-describedby={helpId}
          className="font-mono text-[0.8rem]"
        />
        <Button type="submit" variant="primary" className="sm:w-auto">
          <FolderOpen aria-hidden />
          Use folder
        </Button>
      </div>
      <p id={helpId} className="text-xs text-fg-subtle">
        <span className="font-medium text-pass">Recommended</span> — re-analysis re-reads your folder after you fix
        code. Nothing in it is ever modified.
      </p>
    </form>
  )
}

function ProjectSummary({ project, onReplace }: { project: ProjectView; onReplace: () => void }) {
  const git = project.git
  const rereads = project.source_kind === 'path' || project.source_kind === 'demo'
  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-base leading-snug font-semibold text-fg" title={project.name}>
            {project.name}
          </p>
          <Badge tone="neutral">{SOURCE_LABEL[project.source_kind] ?? project.source_kind}</Badge>
        </div>
        {project.source_path && (
          <p className="mt-1 truncate font-mono text-2xs text-fg-subtle" title={project.source_path}>
            {project.source_path}
          </p>
        )}
      </div>

      <dl className="grid grid-cols-3 gap-2">
        <MiniStat label="Files" value={project.file_count} />
        <MiniStat label="Python files" value={project.python_files} tone={project.python_files ? undefined : 'warning'} />
        <MiniStat label="Language" value={capitalize(project.language || 'python')} />
      </dl>

      <div className="flex flex-wrap items-center gap-1.5" aria-label="Git status">
        {git?.is_repo ? (
          <>
            <Badge tone="info" size="md">
              <GitBranch aria-hidden />
              {git.branch ?? (git.head ? git.head.slice(0, 7) : 'detached')}
            </Badge>
            {git.dirty ? (
              <Tooltip content="Uncommitted changes are analyzed, but only committed files will be submitted.">
                <Badge tone="warning" size="md" tabIndex={0}>
                  {git.modified.length + git.staged.length} uncommitted
                </Badge>
              </Tooltip>
            ) : (
              <Badge tone="pass" size="md">
                Clean
              </Badge>
            )}
            {git.untracked.length > 0 && (
              <Tooltip content="Untracked files will not be part of your git submission.">
                <Badge tone="warning" variant="outline" size="md" tabIndex={0}>
                  {git.untracked.length} untracked
                </Badge>
              </Tooltip>
            )}
          </>
        ) : (
          <Badge tone="neutral" variant="dashed" size="md">
            <GitBranch aria-hidden />
            {git?.error ? 'Git unavailable' : 'Not a git repository'}
          </Badge>
        )}
        {rereads && (
          <Tooltip content="Each new analysis copies this folder again, so your latest edits are picked up.">
            <Badge tone="accent" size="md" tabIndex={0}>
              <RefreshCw aria-hidden />
              Live folder
            </Badge>
          </Tooltip>
        )}
      </div>

      {project.warnings.length > 0 && (
        <ul className="space-y-1 text-xs text-warning">
          {project.warnings.slice(0, 3).map((w, i) => (
            <li key={i} className="flex gap-1.5">
              <Files className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span className="min-w-0 break-words">{w}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <span className="inline-flex items-center gap-1.5 text-xs text-fg-subtle">
          <FileCode2 className="size-3.5" aria-hidden />
          Snapshot ready
        </span>
        <Button size="sm" variant="ghost" onClick={onReplace}>
          <RefreshCw aria-hidden />
          Replace
        </Button>
      </div>
    </div>
  )
}

function capitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}
