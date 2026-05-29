@echo off

setlocal

cd /d "%~dp0.."

echo [INFO] Stopping old processes on ports 5000 and 5173...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^

  "$ports = 5000,5173; " ^

  "foreach ($port in $ports) { " ^

  "  $procIds = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; " ^

  "  foreach ($procId in $procIds) { " ^

  "    try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host ('[INFO] Stopped PID ' + $procId + ' on port ' + $port) } catch { Write-Host ('[WARN] Failed to stop PID ' + $procId + ' on port ' + $port) } " ^

  "  } " ^

  "}"

echo [INFO] Start Flask backend (bind 0.0.0.0):

echo   cd backend ^&^& .venv\Scripts\activate ^&^& python run_flask.py

echo [INFO] Start frontend in another terminal (bind 0.0.0.0):

echo   cd frontend ^&^& npm run dev -- --host 0.0.0.0 --port 5173

echo [INFO] Or run scripts\restart-dev.bat to start both.

echo [INFO] Set PUBLIC_BASE_URL in .env for student QR/join links.
