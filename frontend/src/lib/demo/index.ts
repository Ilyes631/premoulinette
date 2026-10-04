/** Online demo (VITE_DEMO=1): configuration, read-only error and the static transport singleton. */
import { DEMO_DATA_BASE } from './config'
import { createDemoTransport, type DemoTransport } from './transport'

export { DEMO_READ_ONLY_MESSAGE, INSTALL_URL, IS_DEMO, REPO_URL } from './config'
export { DemoReadOnlyError, isDemoReadOnlyError } from './errors'

let transport: DemoTransport | null = null

function sessionStorageOrNull(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

/** The transport used by `apiRequest` in the demo build (created on first use). */
export function demoTransport(): DemoTransport {
  transport ??= createDemoTransport({ baseUrl: DEMO_DATA_BASE, storage: sessionStorageOrNull() })
  return transport
}
