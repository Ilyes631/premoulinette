@echo off
rem Double-click to start PreMoulinette on Windows (first run installs everything it needs).
title PreMoulinette - ne pas fermer cette fenetre pendant l'utilisation
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo  [!] Node.js n'est pas installe. Installe la version LTS depuis https://nodejs.org puis relance ce fichier.
  echo.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" goto setup
if not exist "frontend\node_modules" goto setup
goto run

:setup
echo.
echo  Premiere utilisation : installation (5 minutes environ, une seule fois)...
echo.
call node scripts\setup.mjs
if errorlevel 1 (
  echo.
  echo  [!] L'installation a echoue. Verifie que Python 3.11+ est installe ^(https://www.python.org^)
  echo      en cochant "Add python.exe to PATH", puis relance ce fichier.
  echo.
  pause
  exit /b 1
)

:run
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo.
echo  PreMoulinette demarre. Le navigateur va s'ouvrir sur http://localhost:5173
echo  Pour ARRETER : ferme cette fenetre.
echo.
start "" cmd /c "timeout /t 10 /nobreak >nul & start http://localhost:5173"
call node scripts\dev.mjs
pause
