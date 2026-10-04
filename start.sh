#!/usr/bin/env sh
# One-command bootstrap for macOS/Linux: installs what is missing, then starts PréMoulinette (http://localhost:5173).
set -e
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required: https://nodejs.org" >&2; exit 1; }
if [ ! -x backend/.venv/bin/python ] || [ ! -d frontend/node_modules ]; then
  node scripts/setup.mjs
fi
exec node scripts/dev.mjs
