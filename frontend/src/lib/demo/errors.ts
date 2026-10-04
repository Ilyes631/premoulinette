import { ApiError } from '../api-error'
import { DEMO_READ_ONLY_MESSAGE } from './config'

/**
 * Thrown by the demo transport for every action that needs the local backend (uploads, local
 * folders, saving settings or the contract, AI, Docker). Its message is the friendly demo text;
 * `action` names what was attempted ("Importing a subject"...).
 */
export class DemoReadOnlyError extends ApiError {
  readonly action: string

  constructor(action = 'This action') {
    super(403, DEMO_READ_ONLY_MESSAGE, { demo: true, action })
    this.name = 'DemoReadOnlyError'
    this.action = action
  }
}

export function isDemoReadOnlyError(error: unknown): error is DemoReadOnlyError {
  return error instanceof DemoReadOnlyError
}
