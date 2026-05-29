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

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Missing backend virtualenv python.
  exit /b 1
)

echo [INFO] Starting backend on http://0.0.0.0:5000 ...
start "OnlineQuiz Backend" cmd /k "cd /d %CD%\backend && .venv\Scripts\activate && python run_flask.py"

echo [INFO] Starting frontend on http://0.0.0.0:5173 ...
start "OnlineQuiz Frontend" cmd /k "cd /d %CD%\frontend && npm.cmd run dev -- --host 0.0.0.0 --port 5173"

echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0show-urls.ps1" -Port 5173 -LocalLabel "本機" -NetworkLabel "區網/外網"
echo [INFO] 請在專案根目錄 .env 設定 PUBLIC_BASE_URL 供 QR Code 使用（例：http://你的IP:5173）
echo [INFO] 若外網連線失敗，請以系統管理員執行 scripts\open-firewall.bat
