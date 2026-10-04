/** Pure helpers of the import flow (kept out of component files for fast refresh). */
import type { ImportState } from './import-card'

/** Why the Analyze button is disabled (null when it can run). */
export function analyzeBlocker(subject: ImportState, project: ImportState): string | null {
  if (subject === 'uploading' || project === 'uploading') return 'Waiting for the import to finish…'
  if (subject === 'loading' || project === 'loading') return 'Loading your selection…'
  if (subject !== 'ready' && project !== 'ready') return 'Import a subject and a student project to start.'
  if (subject !== 'ready') return 'Import a subject to start.'
  if (project !== 'ready') return 'Import your student project to start.'
  return null
}

/** Strips the quotes Windows "Copy as path" adds and surrounding blanks. */
export function normalizePathInput(raw: string): string {
  let value = raw.trim()
  if (value.length >= 2 && ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'")))) {
    value = value.slice(1, -1).trim()
  }
  return value
}

/** C:\..., C:/..., \\server\share, /home/..., ~/... */
export function looksAbsolute(path: string): boolean {
  return /^(?:[a-zA-Z]:[\\/]|\\\\|\/|~[\\/]?)/.test(path)
}
