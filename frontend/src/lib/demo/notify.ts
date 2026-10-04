import { toast } from '../toast'
import { DEMO_READ_ONLY_MESSAGE, REPO_URL } from './config'
import { isDemoReadOnlyError } from './errors'

/** Shows the "read-only online demo" toast when `error` is a DemoReadOnlyError. Returns whether it did. */
export function toastDemoReadOnly(error: unknown): boolean {
  if (!isDemoReadOnlyError(error)) return false
  toast({
    title: `${error.action} is not available in the online demo`,
    description: DEMO_READ_ONLY_MESSAGE,
    tone: 'warning',
    durationMs: 8000,
    action: { label: 'Get PréMoulinette on GitHub', href: REPO_URL },
  })
  return true
}
