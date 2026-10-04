/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" in the read-only online demo build (`npm run build:demo`, see `.env.demo`). */
  readonly VITE_DEMO?: string
  /** Public repository linked from the online demo (default: the PréMoulinette GitHub repo). */
  readonly VITE_REPO_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
