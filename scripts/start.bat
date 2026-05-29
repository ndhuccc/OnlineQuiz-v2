@echo off
setlocal
cd /d "%~dp0.."

echo [INFO] Stopping old process on port 3080...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$procIds = Get-NetTCPConnection -LocalPort 3080 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; " ^
  "foreach ($procId in $procIds) { " ^
  "  try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host ('[INFO] Stopped PID ' + $procId + ' on port 3080') } catch { Write-Host ('[WARN] Failed to stop PID ' + $procId + ' on port 3080') } " ^
  "}"

if not exist "backend\.venv\Scripts\activate.bat" (
  echo [ERROR] Missing backend virtualenv. Run:
  echo   cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)

if exist "frontend\dist\index.html" (
  call backend\.venv\Scripts\activate.bat
  cd backend
  python manage.py collectstatic --noinput
  cd ..
) else (
  echo [WARN] Frontend build is missing. Run:
  echo   cd frontend ^&^& npm.cmd install ^&^& npm.cmd run build
  echo   Or from project root: scripts\build-and-start.bat
)

call backend\.venv\Scripts\activate.bat
cd backend
python manage.py migrate --noinput
echo [INFO] Starting Waitress + Flask on http://0.0.0.0:3080 ...
echo [INFO] Open http://localhost:3080/teacher  (do NOT use :5173 unless restart-dev.bat is also running)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0show-urls.ps1" -Port 3080
waitress-serve --host=0.0.0.0 --port=3080 run_flask:app