/** Client-side helpers for subject / project uploads (validation happens again on the server). */

export const SUBJECT_EXTENSIONS = ['.html', '.htm', '.md', '.markdown', '.txt', '.pdf'] as const
export const SUBJECT_ACCEPT = SUBJECT_EXTENSIONS.join(',')
export const ZIP_ACCEPT = '.zip,application/zip,application/x-zip-compressed'

/** Same limits and skipped folders as project/ingest.py, so users get early feedback. */
export const PROJECT_LIMITS = {
  maxFiles: 5000,
  maxTotalBytes: 50 * 1024 * 1024,
  maxFileBytes: 5 * 1024 * 1024,
} as const

export const SKIPPED_UPLOAD_DIRS = new Set([
  'node_modules',
  '.venv',
  'venv',
  'env',
  '.tox',
  '.mypy_cache',
  '.pytest_cache',
])

function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

export function isSubjectFile(file: Pick<File, 'name'>): boolean {
  return (SUBJECT_EXTENSIONS as readonly string[]).includes(extensionOf(file.name))
}

export function isZipFile(file: Pick<File, 'name'>): boolean {
  return extensionOf(file.name) === '.zip'
}

/** POSIX relative path of a file coming from `<input webkitdirectory>` (falls back to its name). */
export function relativePathOf(file: File): string {
  const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath
  return (rel || file.name).replace(/\\/g, '/')
}

/** Name of the picked top folder ("my-project" for "my-project/src/a.py"). */
export function folderNameOf(files: File[]): string | undefined {
  const first = files[0]
  if (!first) return undefined
  const rel = relativePathOf(first)
  const slash = rel.indexOf('/')
  return slash > 0 ? rel.slice(0, slash) : undefined
}

export interface FolderSelection {
  files: File[]
  skipped: number
  totalBytes: number
  /** Human message when the selection exceeds a server limit. */
  error: string | null
}

/** Drops heavy dependency folders and checks limits before uploading a folder. */
export function prepareFolderFiles(input: Iterable<File>): FolderSelection {
  const files: File[] = []
  let skipped = 0
  let totalBytes = 0
  let error: string | null = null
  for (const file of input) {
    const segments = relativePathOf(file).split('/').slice(0, -1)
    if (segments.some((s) => SKIPPED_UPLOAD_DIRS.has(s))) {
      skipped += 1
      continue
    }
    if (file.size > PROJECT_LIMITS.maxFileBytes) {
      error ??= `${relativePathOf(file)} is larger than 5 MB.`
    }
    files.push(file)
    totalBytes += file.size
  }
  if (!files.length) error ??= 'The selected folder is empty.'
  if (files.length > PROJECT_LIMITS.maxFiles) error ??= `Too many files (${files.length} > 5000).`
  if (totalBytes > PROJECT_LIMITS.maxTotalBytes) error ??= 'The project is larger than 50 MB.'
  return { files, skipped, totalBytes, error }
}
