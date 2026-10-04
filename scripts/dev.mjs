// npm run dev — backend (FastAPI, auto-reload) on 127.0.0.1:8765 + frontend (Vite) on localhost:5173.
import { BACKEND, FRONTEND, NPM, VENV_PY, fail, frontendReady, killTree, log, spawnPrefixed, venvReady } from './lib.mjs'

if (!venvReady() || !frontendReady()) fail('Dependencies missing. Run first: npm run setup')

const children = []
let shuttingDown = false

function shutdown(code = 0) {
  if (shuttingDown) return
  shuttingDown = true
  children.forEach(killTree)
  process.exit(code)
}

const api = spawnPrefixed('api', VENV_PY, ['-m', 'premoulinette', '--reload'], {
  cwd: BACKEND,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
})
children.push(api)

let announced = false
const web = spawnPrefixed('web', NPM, ['run', 'dev'], {
  cwd: FRONTEND,
  onLine: (line) => {
    if (!announced && /Local:/.test(line)) {
      announced = true
      log('ok', 'PréMoulinette is ready → \x1b[1mhttp://localhost:5173\x1b[0m  (Ctrl+C to stop)')
    }
  },
})
children.push(web)

for (const child of children) {
  child.on('exit', (code) => {
    if (!shuttingDown) {
      log('api', `a process exited (code ${code}); stopping everything`)
      shutdown(code ?? 1)
    }
  })
}
process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))
