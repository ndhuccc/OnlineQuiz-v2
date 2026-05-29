@echo off
setlocal
cd /d "%~dp0..\frontend"

REM 使用 npm.cmd 避開 PowerShell 禁止執行 npm.ps1
where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 找不到 npm，請安裝 Node.js LTS
  exit /b 1
)

if "%PYTHON%"=="" (
  if exist "..\backend\.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0..\backend\.venv\Scripts\python.exe"
    echo [INFO] PYTHON=%PYTHON%
  )
)

call npm.cmd run test:e2e
exit /b %ERRORLEVEL%
