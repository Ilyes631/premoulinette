// npm test — backend pytest + frontend vitest. `node scripts/test.mjs backend|frontend` runs one side.
import { FRONTEND, NPM, ROOT, VENV_PY, fail, log, run, venvReady } from './lib.mjs'

const only = process.argv[2]
if (only !== 'frontend') {
  if (!venvReady()) fail('Run first: npm run setup')
  log('api', 'pytest backend/tests')
  run(VENV_PY, ['-m', 'pytest', 'backend/tests', '-q'], { cwd: ROOT })
}
if (only !== 'backend') {
  log('web', 'vitest')
  run(NPM, ['test'], { cwd: FRONTEND })
}
log('ok', 'All tests passed')
