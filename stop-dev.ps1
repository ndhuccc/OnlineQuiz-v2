# OnlineQuiz-v2 dev environment stopper
# Kills the Flask (5000) and Vite (5173) processes started by start-dev.ps1.

$ErrorActionPreference = "Continue"

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

Write-Host "=== Stopping Flask :5000 ==="
Stop-Port 5000
Write-Host "=== Stopping Vite :5173 ==="
Stop-Port 5173
Write-Host "Done."
