// npm run start — production-like single process: build the SPA if needed, then serve UI + API on 127.0.0.1:8765.
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { BACKEND, FRONTEND, NPM, VENV_PY, fail, frontendReady, log, run, venvReady } from './lib.mjs'

if (!venvReady() || !frontendReady()) fail('Dependencies missing. Run first: npm run setup')

if (!existsSync(join(FRONTEND, 'dist', 'index.html')) || process.argv.includes('--build')) {
  log('web', 'Building the frontend…')
  run(NPM, ['run', 'build'], { cwd: FRONTEND })
}
log('ok', 'Starting PréMoulinette on http://127.0.0.1:8765')
run(VENV_PY, ['-m', 'premoulinette', '--open'], { cwd: BACKEND })
