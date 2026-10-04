/** Parser for the minimal unified diffs produced by explain/fixes.py (display only). */

export type PatchLineKind = 'file' | 'hunk' | 'add' | 'del' | 'context' | 'meta'

export interface PatchLine {
  kind: PatchLineKind
  /** Line content without its +/-/space prefix (headers keep their full text). */
  text: string
  oldNo: number | null
  newNo: number | null
}

const HUNK_RE = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/

export function parseUnifiedDiff(patch: string): PatchLine[] {
  const out: PatchLine[] = []
  let oldNo = 0
  let newNo = 0
  const lines = patch.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n')
  for (const raw of lines) {
    if (raw.startsWith('--- ') || raw.startsWith('+++ ')) {
      out.push({ kind: 'file', text: raw, oldNo: null, newNo: null })
      continue
    }
    const hunk = HUNK_RE.exec(raw)
    if (hunk) {
      oldNo = Number(hunk[1])
      newNo = Number(hunk[2])
      out.push({ kind: 'hunk', text: raw, oldNo: null, newNo: null })
      continue
    }
    if (raw.startsWith('+')) {
      out.push({ kind: 'add', text: raw.slice(1), oldNo: null, newNo: newNo++ })
    } else if (raw.startsWith('-')) {
      out.push({ kind: 'del', text: raw.slice(1), oldNo: oldNo++, newNo: null })
    } else if (raw.startsWith(' ') || raw === '') {
      out.push({ kind: 'context', text: raw.slice(1), oldNo: oldNo++, newNo: newNo++ })
    } else {
      out.push({ kind: 'meta', text: raw, oldNo: null, newNo: null })
    }
  }
  return out
}
