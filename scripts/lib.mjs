// Shared helpers for the dev scripts (Node built-ins only, cross-platform, Windows first).
import { spawn, spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
export const BACKEND = join(ROOT, 'backend')
export const FRONTEND = join(ROOT, 'frontend')
export const IS_WIN = process.platform === 'win32'
export const VENV_PY = IS_WIN
  ? join(BACKEND, '.venv', 'Scripts', 'python.exe')
  : join(BACKEND, '.venv', 'bin', 'python')
export const NPM = IS_WIN ? 'npm.cmd' : 'npm'

const COLORS = { api: '\x1b[38;5;141m', web: '\x1b[38;5;45m', setup: '\x1b[38;5;214m', ok: '\x1b[32m', err: '\x1b[31m' }
const RESET = '\x1b[0m'

export function log(tag, message) {
  process.stdout.write(`${COLORS[tag] ?? ''}[${tag}]${RESET} ${message}\n`)
}

export function fail(message) {
  process.stderr.write(`${COLORS.err}✖ ${message}${RESET}\n`)
  process.exit(1)
}

/** Run a command synchronously, inheriting stdio. Exits the script on failure. */
export function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', shell: IS_WIN && cmd.endsWith('.cmd'), ...opts })
  if (res.status !== 0) fail(`${cmd} ${args.join(' ')} failed (exit ${res.status ?? res.error?.message})`)
}

/** Find a Python >= 3.11 interpreter: py -3, python, python3. Returns [cmd, ...prefixArgs]. */
export function findPython() {
  const candidates = IS_WIN ? [['py', '-3'], ['python'], ['python3']] : [['python3'], ['python']]
  for (const [cmd, ...pre] of candidates) {
    const res = spawnSync(cmd, [...pre, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], { encoding: 'utf8' })
    if (res.status === 0) {
      const [major, minor] = res.stdout.trim().split('.').map(Number)
      if (major === 3 && minor >= 11) return [cmd, ...pre]
    }
  }
  return null
}

export function venvReady() {
  return existsSync(VENV_PY)
}

export function frontendReady() {
  return existsSync(join(FRONTEND, 'node_modules'))
}

/** Spawn a long-running child with prefixed, colored output. */
export function spawnPrefixed(tag, cmd, args, opts = {}) {
  const child = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], shell: IS_WIN && cmd.endsWith('.cmd'), ...opts })
  const pipe = (stream, out) => {
    let buffer = ''
    stream.setEncoding('utf8')
    stream.on('data', (chunk) => {
      buffer += chunk
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ''
      for (const line of lines) out.write(`${COLORS[tag] ?? ''}[${tag}]${RESET} ${line}\n`)
      if (opts.onLine) lines.forEach(opts.onLine)
    })
  }
  pipe(child.stdout, process.stdout)
  pipe(child.stderr, process.stderr)
  return child
}

/** Kill a child and its whole process tree. */
export function killTree(child) {
  if (!child || child.exitCode !== null) return
  if (IS_WIN) spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  else child.kill('SIGTERM')
}
