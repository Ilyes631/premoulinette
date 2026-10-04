/**
 * Error type of the API client (kept out of `api.ts` so the transports can throw it without an
 * import cycle). `api.ts` re-exports everything here: import from `@/lib/api` in features.
 */
import type { ValidationErrorItem } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  /** True when the server could not be reached at all. */
  get isNetworkError(): boolean {
    return this.status === 0
  }

  /** FastAPI 422 items (`[{loc, msg}]`), empty for any other error. */
  get validationErrors(): ValidationErrorItem[] {
    return Array.isArray(this.detail) ? this.detail.filter(isValidationItem) : []
  }
}

function isValidationItem(value: unknown): value is ValidationErrorItem {
  return typeof value === 'object' && value !== null && 'msg' in value && 'loc' in value
}

/** Human-readable message out of a FastAPI `detail` payload (string, list of items or object). */
export function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail.trim() || null
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (isValidationItem(item)) {
        const loc = item.loc.filter((p) => p !== 'body').join('.')
        return loc ? `${loc}: ${item.msg}` : item.msg
      }
      return typeof item === 'string' ? item : JSON.stringify(item)
    })
    return parts.length ? parts.join('; ') : null
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as Record<string, unknown>
    if (typeof obj.message === 'string') return obj.message
    if (typeof obj.detail === 'string') return obj.detail
  }
  return null
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

/** Best message for any thrown value (used by toasts and error cards). */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return typeof error === 'string' ? error : 'Unexpected error'
}
