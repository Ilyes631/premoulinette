/**
 * Shape of `public/demo-data/manifest.json`, written by `backend/scripts/export_demo_data.py`.
 * Keep `requestKey` in sync with `request_key` in that script.
 */

/** A response: a JSON file of the demo data, or a recorded API error. */
export interface ManifestResponse {
  file?: string
  status?: number
  detail?: unknown
}

/** Response that changes once an analysis exists (`after` = its id; `null` = from the start). */
export interface ManifestVariant extends ManifestResponse {
  after: string | null
}

export type ManifestRoute = string | ManifestResponse | ManifestVariant[]

export interface ManifestAnalysis {
  number: number
  subject_id: string
  project_id: string
  created_at: string
  readiness: number
  verdict: string
}

export interface DemoManifest {
  version: number
  app_version?: string
  subject_id: string
  /** project id -> analysis ids in run order (#1, #2...). */
  runs: Record<string, string[]>
  analyses: Record<string, ManifestAnalysis>
  routes: Record<string, ManifestRoute>
  /** analysis id -> language -> bundle file `{check_id: {explain, fix, expected}}`. */
  explain: Record<string, Record<string, string>>
  /** analysis id -> format -> static export file. */
  exports: Record<string, Record<string, string>>
}

export type QueryValue = string | number | boolean | null | undefined

/**
 * `"GET /api/analyses?limit=5"`: method, decoded path, then the non-empty query parameters sorted
 * by name (decoded, not escaped). The same rule as `request_key()` of the export script.
 */
export function requestKey(method: string, path: string, query?: Record<string, QueryValue>): string {
  const params = Object.entries(query ?? {})
    .filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
    .map(([name, value]) => [name, String(value)] as const)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
  const qs = params.map(([name, value]) => `${name}=${value}`).join('&')
  return `${method.toUpperCase()} ${path}${qs ? `?${qs}` : ''}`
}

/** `/analyses/demo-1/checks/test%3Ax%231/explain` -> `/analyses/demo-1/checks/test:x#1/explain`. */
export function decodePath(path: string): string {
  const absolute = path.startsWith('/') ? path : `/${path}`
  return absolute
    .split('/')
    .map((segment) => {
      try {
        return decodeURIComponent(segment)
      } catch {
        return segment
      }
    })
    .join('/')
}

/** The entry of a route that applies given the analyses that exist (`isDone(id)`). */
export function pickResponse(route: ManifestRoute, isDone: (analysisId: string) => boolean): ManifestResponse {
  if (typeof route === 'string') return { file: route }
  if (!Array.isArray(route)) return route
  let picked: ManifestVariant | undefined
  for (const variant of route) {
    if (variant.after === null || isDone(variant.after)) picked = variant
  }
  return picked ?? route[0] ?? { status: 404, detail: 'Not found' }
}
