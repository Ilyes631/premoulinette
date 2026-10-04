// npm run setup — create the Python venv, install the backend and the frontend dependencies.
import { BACKEND, FRONTEND, NPM, VENV_PY, findPython, log, fail, run, venvReady } from './lib.mjs'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

if (!venvReady()) {
  const python = findPython()
  if (!python) fail('Python 3.11+ not found. Install it from https://www.python.org/downloads/ and retry.')
  log('setup', `Creating backend/.venv with ${python.join(' ')}`)
  run(python[0], [...python.slice(1), '-m', 'venv', join(BACKEND, '.venv')])
}

log('setup', 'Installing backend (pip install -e backend[dev])')
run(VENV_PY, ['-m', 'pip', 'install', '--disable-pip-version-check', '-q', '--upgrade', 'pip'])
run(VENV_PY, ['-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-e', `${BACKEND}[dev]`])

log('setup', 'Installing frontend dependencies')
run(NPM, [existsSync(join(FRONTEND, 'package-lock.json')) ? 'ci' : 'install', '--no-audit', '--no-fund'], { cwd: FRONTEND })

log('ok', 'Setup complete. Run: npm run dev')
