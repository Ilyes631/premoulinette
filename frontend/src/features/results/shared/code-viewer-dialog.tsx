import { ExternalLink, FileX2 } from 'lucide-react'
import {
  Button,
  CodeBlock,
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Skeleton,
  languageFromPath,
} from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { IS_DEMO } from '@/lib/demo/config'
import { useProjectFile } from '@/lib/queries'
import type { FileTarget } from './results-context'
import { vscodeUrl } from './selectors'

interface CodeViewerDialogProps {
  projectId: string
  /** Original local folder of the project (enables "Open in VS Code"). */
  projectPath: string | null
  target: FileTarget | null
  onClose: () => void
}

/** Read-only viewer of one student file, scrolled to and highlighting the relevant line. */
export function CodeViewerDialog({ projectId, projectPath, target, onClose }: CodeViewerDialogProps) {
  const file = useProjectFile(projectId, target?.file)
  const line = target?.line ?? null
  // The online demo has no local folder to open.
  const vscode = target && !IS_DEMO ? vscodeUrl(projectPath, target.file, line) : null

  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm break-all">{target?.file}</DialogTitle>
          <DialogDescription>{line ? `Line ${line} · read-only view of your project` : 'Read-only view of your project'}</DialogDescription>
        </DialogHeader>
        <DialogBody className="p-0">
          {file.isPending && target && (
            <div className="space-y-2 p-5" aria-busy>
              {Array.from({ length: 10 }, (_, i) => (
                <Skeleton key={i} className="h-4" style={{ width: `${40 + ((i * 37) % 55)}%` }} />
              ))}
            </div>
          )}
          {file.isError && (
            <div className="flex flex-col items-center gap-2 px-5 py-12 text-center" role="alert">
              <FileX2 className="size-6 text-fg-subtle" aria-hidden />
              <p className="text-sm font-medium text-fg">This file cannot be displayed</p>
              <p className="max-w-md text-xs text-fg-muted">{errorMessage(file.error)}</p>
            </div>
          )}
          {file.data && (
            <CodeBlock
              code={file.data.content}
              language={languageFromPath(file.data.path)}
              highlight={line ? [line] : []}
              focusLine={line ?? undefined}
              maxHeight="min(65vh, 42rem)"
              className="rounded-none border-0"
              copyable
              title={`${file.data.content.split('\n').length} lines`}
            />
          )}
        </DialogBody>
        <DialogFooter className="items-center">
          {vscode && (
            <a
              href={vscode}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border-strong px-3.5 text-sm font-medium text-fg transition-colors hover:bg-surface-2"
            >
              <ExternalLink className="size-4" aria-hidden />
              Open in VS Code
            </a>
          )}
          <DialogClose asChild>
            <Button variant="secondary">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
