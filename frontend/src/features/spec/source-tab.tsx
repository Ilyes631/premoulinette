import { FileText, RotateCw, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState, type ReactNode } from 'react'
import { Badge, Button, Card, EmptyState, Input, Skeleton } from '@/components/ui'
import { errorMessage } from '@/lib/api'
import { useSubjectDocument } from '@/lib/queries'

function highlight(line: string, needle: string): ReactNode {
  if (!needle) return line
  const lower = line.toLowerCase()
  const parts: ReactNode[] = []
  let from = 0
  let index = lower.indexOf(needle, from)
  while (index !== -1) {
    if (index > from) parts.push(line.slice(from, index))
    parts.push(
      <mark key={index} className="rounded-[2px] bg-warning/30 text-fg">
        {line.slice(index, index + needle.length)}
      </mark>,
    )
    from = index + needle.length
    index = lower.indexOf(needle, from)
  }
  if (from < line.length) parts.push(line.slice(from))
  return parts
}

export function SourceTab({ subjectId, sourceName }: { subjectId: string; sourceName: string }) {
  const query = useSubjectDocument(subjectId)
  const [search, setSearch] = useState('')
  const needle = useDeferredValue(search.trim().toLowerCase())
  const [onlyMatches, setOnlyMatches] = useState(false)

  const lines = useMemo(() => (query.data?.text ?? '').split('\n'), [query.data])
  const matches = useMemo(
    () => (needle ? lines.reduce((n, l) => n + (l.toLowerCase().includes(needle) ? 1 : 0), 0) : 0),
    [lines, needle],
  )

  if (query.isPending) return <Skeleton className="h-96" />
  if (query.isError) {
    return (
      <EmptyState icon={FileText} tone="fail" title="The subject text could not be loaded" description={errorMessage(query.error)}>
        <Button onClick={() => void query.refetch()}>
          <RotateCw aria-hidden /> Retry
        </Button>
      </EmptyState>
    )
  }
  if (!query.data.text.trim()) {
    return <EmptyState icon={FileText} title="No text was extracted" description="The subject file did not contain readable text (scanned PDF?)." />
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <FileText className="size-4 text-fg-muted" aria-hidden />
        <h3 className="min-w-0 truncate text-sm font-semibold text-fg">{sourceName}</h3>
        <Badge className="uppercase">{query.data.media_type}</Badge>
        <div className="relative ml-auto w-full sm:w-64">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-fg-subtle" aria-hidden />
          <Input
            type="search"
            aria-label="Search the subject text"
            placeholder="Search the subject…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 text-xs"
          />
        </div>
        {needle && (
          <span className="flex items-center gap-2 text-xs text-fg-muted" aria-live="polite">
            <span className="tabular">
              {matches} matching line{matches === 1 ? '' : 's'}
            </span>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={onlyMatches} onChange={(e) => setOnlyMatches(e.target.checked)} className="accent-accent" />
              only matches
            </label>
          </span>
        )}
      </div>
      <div className="max-h-[70vh] overflow-auto bg-code-bg py-2">
        <table className="w-full border-collapse font-mono text-[0.8125rem] leading-6">
          <tbody>
            {lines.map((line, i) => {
              const hit = needle !== '' && line.toLowerCase().includes(needle)
              if (onlyMatches && needle && !hit) return null
              return (
                <tr key={i} className={hit ? 'bg-warning/6' : undefined}>
                  <td className="tabular w-12 pr-3 pl-3 text-right align-top text-fg-subtle select-none">{i + 1}</td>
                  <td className="pr-4 whitespace-pre-wrap text-fg [overflow-wrap:anywhere]">{hit ? highlight(line, needle) : line || ' '}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
