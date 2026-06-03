# OnlineQuiz-v2 dev environment starter
# Starts Flask (port 5000) and Vite (port 5173) as background processes.
# Output is redirected to backend\flask.{log,err} and frontend\vite.{out,err}.log.

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

function Stop-Port {
    param([int]$Port)
    $pids = @(
        netstat -ano |
            Select-String ":$Port.*LISTENING" |
            ForEach-Object { if ($_ -match '\s(\d+)\s*$') { $matches[1] } } |
            Sort-Object -Unique
    )
    foreach ($p in $pids) {
        if ($p -match '^\d+$') {
            try {
                Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
                Write-Host "  killed PID $p on :$Port"
            } catch {}
        }
    }
}

Write-Host "=== Stopping stale processes ==="
Stop-Port 5000
Stop-Port 5173
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "=== Starting Flask (backend :5000) ==="
$flask = Start-Process `
    -FilePath "$root\backend\.venv\Scripts\python.exe" `
    -ArgumentList "run_flask.py" `
    -WorkingDirectory "$root\backend" `
    -RedirectStandardOutput "$root\backend\flask.log" `
    -RedirectStandardError "$root\backend\flask.err" `
    -WindowStyle Hidden `
    -PassThru

Write-Host "  PID $($flask.Id) -> $root\backend\flask.log"

Write-Host ""
Write-Host "=== Starting Vite (frontend :5173) ==="
$vite = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c","`"$root\frontend\node_modules\.bin\vite.cmd`" --host 127.0.0.1 --port 5173" `
    -WorkingDirectory "$root\frontend" `
    -RedirectStandardOutput "$root\frontend\vite.out.log" `
    -RedirectStandardError "$root\frontend\vite.err.log" `
    -WindowStyle Hidden `
    -PassThru

Write-Host "  PID $($vite.Id) -> $root\frontend\vite.out.log"

Start-Sleep -Seconds 4

Write-Host ""
Write-Host "=== Status ==="
$flaskOk = (netstat -ano | Select-String ":5000.*LISTENING") -ne $null
$viteOk  = (netstat -ano | Select-String ":5173.*LISTENING") -ne $null

if ($flaskOk) { Write-Host "  Flask  :5000  UP" } else { Write-Host "  Flask  :5000  DOWN (see backend\flask.err)" -ForegroundColor Red }
if ($viteOk)  { Write-Host "  Vite   :5173  UP" } else { Write-Host "  Vite   :5173  DOWN (see frontend\vite.err.log)" -ForegroundColor Red }

Write-Host ""
Write-Host "Open http://127.0.0.1:5173  (frontend, proxies /api -> Flask)"
Write-Host ""
Write-Host "Tail logs:"
Write-Host "  Get-Content '$root\backend\flask.log' -Wait"
Write-Host "  Get-Content '$root\frontend\vite.out.log' -Wait"
Write-Host ""
Write-Host "Stop:  .\stop-dev.ps1"
