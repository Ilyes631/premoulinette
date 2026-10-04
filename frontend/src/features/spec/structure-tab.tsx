import { File, Folder, Plus, RotateCcw, Save, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, Input, ProvenanceBadge, Switch } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { FileRequirement, PracticalSpec, StructureSpec } from '@/lib/types'
import { ChipInput, SectionTitle } from './parts'
import { buildTree, cloneSpec, userOrigin, type TreeNode } from './spec-utils'

function TreeRows({ nodes, depth }: { nodes: TreeNode[]; depth: number }) {
  return (
    <>
      {nodes.map((node) => {
        const isDir = node.children.length > 0 || node.file?.kind === 'directory'
        const file = node.file
        return (
          <li key={node.path}>
            <div className="flex min-h-7 items-center gap-2 rounded-md px-2 hover:bg-surface-2" style={{ paddingLeft: `${depth * 16 + 8}px` }}>
              {isDir ? (
                <Folder className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
              ) : (
                <File className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
              )}
              <span className={cn('min-w-0 truncate font-mono text-[0.8125rem]', file ? 'text-fg' : 'text-fg-muted')}>
                {node.name}
                {isDir && '/'}
              </span>
              {file && (
                <span className="ml-auto flex shrink-0 items-center gap-1">
                  {file.bonus ? (
                    <Badge tone="bonus">Bonus</Badge>
                  ) : file.required ? (
                    <Badge tone="pass">Required</Badge>
                  ) : (
                    <Badge>Optional</Badge>
                  )}
                  {file.origin.provenance !== 'explicit' && (
                    <ProvenanceBadge provenance={file.origin.provenance} confidence={file.origin.confidence} />
                  )}
                </span>
              )}
            </div>
            {node.children.length > 0 && (
              <ul>
                <TreeRows nodes={node.children} depth={depth + 1} />
              </ul>
            )}
          </li>
        )
      })}
    </>
  )
}

export interface StructureTabProps {
  spec: PracticalSpec
  saving: boolean
  onSave: (spec: PracticalSpec) => Promise<boolean>
}

export function StructureTab({ spec, saving, onSave }: StructureTabProps) {
  const [draft, setDraft] = useState<StructureSpec>(() => cloneSpec(spec.structure))
  const [base, setBase] = useState(spec.structure)
  const [editing, setEditing] = useState(false)
  if (base !== spec.structure) {
    setBase(spec.structure)
    setDraft(cloneSpec(spec.structure))
  }
  const dirty = JSON.stringify(draft) !== JSON.stringify(spec.structure)
  const set = (patch: Partial<StructureSpec>) => setDraft((d) => ({ ...d, ...patch }))
  const setFile = (index: number, patch: Partial<FileRequirement>) =>
    setDraft((d) => ({
      ...d,
      files: d.files.map((f, i) => (i === index ? { ...f, ...patch, origin: userOrigin(f.origin) } : f)),
    }))

  const tree = buildTree(draft.files)
  const counts = {
    required: draft.files.filter((f) => f.required && !f.bonus).length,
    optional: draft.files.filter((f) => !f.required && !f.bonus).length,
    bonus: draft.files.filter((f) => f.bonus).length,
  }

  const save = async () => {
    const files = draft.files
      .map((f) => ({ ...f, path: f.path.trim(), required: f.bonus ? false : f.required }))
      .filter((f) => f.path)
    const ok = await onSave({ ...spec, structure: { ...draft, files, origin: dirty ? userOrigin(draft.origin) : draft.origin } })
    if (ok) setEditing(false)
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <Card className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3.5">
          <h3 className="text-sm font-semibold text-fg">Expected tree</h3>
          <span className="tabular text-xs text-fg-muted">
            {counts.required} required · {counts.optional} optional · {counts.bonus} bonus
          </span>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setEditing((v) => !v)} aria-expanded={editing}>
            {editing ? 'Show tree' : 'Edit list'}
          </Button>
        </div>
        {editing ? (
          <div className="space-y-2 px-4 py-4">
            <ul className="space-y-1.5">
              {draft.files.map((file, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-2/40 px-2.5 py-2">
                  <Input
                    aria-label={`Path ${i + 1}`}
                    value={file.path}
                    spellCheck={false}
                    placeholder="folder/file.py"
                    onChange={(e) => setFile(i, { path: e.target.value })}
                    className="h-8 min-w-48 flex-1 font-mono text-[0.8125rem]"
                  />
                  <select
                    aria-label={`Kind of ${file.path || `entry ${i + 1}`}`}
                    value={file.kind}
                    onChange={(e) => setFile(i, { kind: e.target.value as FileRequirement['kind'] })}
                    className="h-8 rounded-md border border-border-strong bg-bg-subtle px-1.5 text-xs text-fg"
                  >
                    <option value="file">File</option>
                    <option value="directory">Folder</option>
                  </select>
                  <Switch size="sm" label="Required" checked={file.required && !file.bonus} disabled={file.bonus} onCheckedChange={(v) => setFile(i, { required: v })} />
                  <Switch size="sm" label="Bonus" checked={file.bonus} onCheckedChange={(v) => setFile(i, { bonus: v, required: v ? false : file.required })} />
                  <button
                    type="button"
                    onClick={() => set({ files: draft.files.filter((_, j) => j !== i) })}
                    className="inline-flex size-8 items-center justify-center rounded-md text-fg-muted hover:bg-surface-3 hover:text-fail"
                    aria-label={`Remove ${file.path || `entry ${i + 1}`}`}
                    title="Remove"
                  >
                    <Trash2 className="size-3.5" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                set({
                  files: [
                    ...draft.files,
                    { path: '', kind: 'file', required: true, bonus: false, description: null, origin: userOrigin() },
                  ],
                })
              }
            >
              <Plus aria-hidden /> Add path
            </Button>
          </div>
        ) : tree.length ? (
          <ul className="px-2 py-3" aria-label="Expected files">
            <TreeRows nodes={tree} depth={0} />
          </ul>
        ) : (
          <p className="px-5 py-6 text-sm text-fg-subtle">No expected file. Exercise files are still checked.</p>
        )}
      </Card>

      <div className="space-y-4">
        <Card>
          <div className="space-y-3 px-5 py-4">
            <SectionTitle>Repository rules</SectionTitle>
            <Switch label="Require a .gitignore" checked={draft.require_gitignore} onCheckedChange={(v) => set({ require_gitignore: v })} />
            <Switch
              label="Parasite files are errors"
              checked={draft.forbidden_patterns_are_errors}
              onCheckedChange={(v) => set({ forbidden_patterns_are_errors: v })}
            />
            <Switch label="Allow extra files" checked={draft.allow_extra_files} onCheckedChange={(v) => set({ allow_extra_files: v })} />
          </div>
        </Card>
        <Card>
          <div className="px-5 py-4">
            <ChipInput
              label="Forbidden patterns"
              tone="fail"
              values={draft.forbidden_patterns}
              placeholder="__pycache__/, *.pyc…"
              onChange={(v) => set({ forbidden_patterns: v })}
            />
            <p className="mt-2 text-xs text-fg-muted">
              {draft.forbidden_patterns_are_errors
                ? 'Matching files fail the analysis (the subject forbids them).'
                : 'Matching files are reported as warnings.'}
            </p>
          </div>
        </Card>
        <div className="flex justify-end gap-2">
          {dirty && (
            <Button size="sm" variant="ghost" onClick={() => setDraft(cloneSpec(spec.structure))}>
              <RotateCcw aria-hidden /> Discard
            </Button>
          )}
          <Button size="sm" variant="primary" disabled={!dirty} loading={saving} onClick={save}>
            <Save aria-hidden /> Save structure
          </Button>
        </div>
      </div>
    </div>
  )
}
