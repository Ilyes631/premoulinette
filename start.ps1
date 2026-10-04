# One-command bootstrap for Windows: installs what is missing, then starts PréMoulinette (http://localhost:5173).
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Error 'Node.js 20+ is required: https://nodejs.org' }
if (-not (Test-Path 'backend\.venv\Scripts\python.exe') -or -not (Test-Path 'frontend\node_modules')) {
  node scripts/setup.mjs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
node scripts/dev.mjs
