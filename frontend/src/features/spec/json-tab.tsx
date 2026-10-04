import { Braces, CheckCircle2, Download, RotateCcw, Save } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button, Card } from '@/components/ui'
import type { PracticalSpec } from '@/lib/types'
import { IssueList } from './parts'
import { parseSpecJson, type DraftIssue } from './spec-utils'

export interface JsonTabProps {
  spec: PracticalSpec
  fileName: string
  saving: boolean
  serverErrors: DraftIssue[]
  onSave: (spec: PracticalSpec) => Promise<boolean>
}

const pretty = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`

export function JsonTab({ spec, fileName, saving, serverErrors, onSave }: JsonTabProps) {
  const [text, setText] = useState(() => pretty(spec))
  const [base, setBase] = useState(spec)
  const [issues, setIssues] = useState<DraftIssue[]>([])
  const [validMessage, setValidMessage] = useState<string | null>(null)
  const gutterRef = useRef<HTMLPreElement>(null)

  if (base !== spec) {
    setBase(spec)
    setText(pretty(spec))
    setIssues([])
  }
  const dirty = text !== pretty(spec)
  const lineCount = text.split('\n').length

  const validate = () => {
    const result = parseSpecJson(text)
    setIssues(result.issues)
    setValidMessage(result.spec ? 'Valid JSON. The server checks the full schema when you save.' : null)
    return result.spec
  }

  const format = () => {
    try {
      setText(pretty(JSON.parse(text)))
      setIssues([])
    } catch {
      validate()
    }
  }

  const save = async () => {
    const parsed = validate()
    if (parsed) await onSave(parsed)
  }

  const download = () => {
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <Braces className="size-4 text-fg-muted" aria-hidden />
        <h3 className="text-sm font-semibold text-fg">PracticalSpec JSON</h3>
        <span className="tabular text-xs text-fg-subtle">{lineCount} lines</span>
        {dirty && <span className="text-xs text-warning">Unsaved changes</span>}
        <div className="ml-auto flex flex-wrap gap-1.5">
          <Button size="sm" variant="ghost" onClick={format}>
            Format
          </Button>
          <Button size="sm" variant="ghost" onClick={validate}>
            <CheckCircle2 aria-hidden /> Validate
          </Button>
          <Button size="sm" variant="ghost" onClick={download} aria-label="Download the contract as JSON">
            <Download aria-hidden /> Download
          </Button>
          {dirty && (
            <Button size="sm" variant="ghost" onClick={() => { setText(pretty(spec)); setIssues([]) }}>
              <RotateCcw aria-hidden /> Reset
            </Button>
          )}
          <Button size="sm" variant="primary" disabled={!dirty} loading={saving} onClick={save}>
            <Save aria-hidden /> Save JSON
          </Button>
        </div>
      </div>
      {(issues.length > 0 || serverErrors.length > 0 || validMessage) && (
        <div className="space-y-2 border-b border-border px-4 py-3">
          <IssueList issues={issues} title="Invalid contract" />
          <IssueList issues={serverErrors} title="The server rejected the contract" />
          {validMessage && !issues.length && <p className="text-xs text-pass">{validMessage}</p>}
        </div>
      )}
      <div className="flex max-h-[70vh] min-h-80 bg-code-bg">
        <pre
          ref={gutterRef}
          aria-hidden
          className="tabular w-12 shrink-0 overflow-hidden border-r border-border py-3 pr-2 text-right font-mono text-[0.75rem] leading-5 text-fg-subtle select-none"
        >
          {Array.from({ length: lineCount }, (_, i) => i + 1).join('\n')}
        </pre>
        <textarea
          aria-label="Contract JSON"
          value={text}
          spellCheck={false}
          wrap="off"
          onChange={(e) => {
            setText(e.target.value)
            setValidMessage(null)
          }}
          onScroll={(e) => {
            if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop
          }}
          className="min-h-80 flex-1 resize-none overflow-auto bg-transparent px-3 py-3 font-mono text-[0.75rem] leading-5 whitespace-pre text-fg outline-none"
        />
      </div>
      <p className="border-t border-border px-4 py-2 text-2xs text-fg-subtle">
        Saving replaces the whole contract and marks it as reviewed. Use Format to re-indent.
      </p>
    </Card>
  )
}
