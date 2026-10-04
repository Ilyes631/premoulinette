/**
 * Read-only online demo (`npm run build:demo`, VITE_DEMO=1): the SPA runs without a backend and
 * answers its API calls from the static files of `public/demo-data` (see `transport.ts`).
 */

/** True in the static demo build. Statically replaced by Vite: dead demo code is dropped otherwise. */
export const IS_DEMO = import.meta.env.VITE_DEMO === '1'

const DEFAULT_REPO_URL = 'https://github.com/Ilyes631/premoulinette'

/** Public repository of the project (override with VITE_REPO_URL). */
export const REPO_URL = (import.meta.env.VITE_REPO_URL ?? '').trim().replace(/\/+$/, '') || DEFAULT_REPO_URL

/** README section explaining how to install and run PréMoulinette locally. */
export const INSTALL_URL = `${REPO_URL}#installation`

/** Folder of the exported demo responses (served next to the SPA). */
export const DEMO_DATA_BASE = `${import.meta.env.BASE_URL ?? '/'}demo-data/`

export const DEMO_READ_ONLY_MESSAGE =
  'This is a read-only online demo. Install PréMoulinette locally to analyze your own project.'
