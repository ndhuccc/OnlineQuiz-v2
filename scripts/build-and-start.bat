@echo off
setlocal
cd /d "%~dp0.."

echo [INFO] Building frontend (using npm.cmd to avoid PowerShell policy issues)...
if not exist "frontend\node_modules" (
  echo [INFO] Running npm install...
  pushd frontend
  call npm.cmd install
  if errorlevel 1 (
    popd
    echo [ERROR] npm install failed.
    exit /b 1
  )
  popd
)

pushd frontend
call npm.cmd run build
if errorlevel 1 (
  popd
  echo [ERROR] npm run build failed.
  exit /b 1
)
popd

if not exist ".env" (
  echo [WARN] .env not found. Creating from .env.example ...
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [INFO] Edit .env and set PUBLIC_BASE_URL to your LAN/public URL, then run this script again.
  ) else (
    echo [WARN] Missing .env.example. Create .env with PUBLIC_BASE_URL=http://YOUR_IP:3080
  )
)

echo [INFO] Starting production server...
call "%~dp0start.bat"
