@echo off
setlocal
cd /d "%~dp0..\backend"

set "QUIZ_DB_PATH=%~dp0..\data\e2e-quiz.db"
set "DJANGO_SETTINGS_MODULE=config.settings_flask"

if exist "%QUIZ_DB_PATH%" del /f /q "%QUIZ_DB_PATH%" 2>nul
if exist "%QUIZ_DB_PATH%-wal" del /f /q "%QUIZ_DB_PATH%-wal" 2>nul
if exist "%QUIZ_DB_PATH%-shm" del /f /q "%QUIZ_DB_PATH%-shm" 2>nul

if defined PYTHON (
  set "PY=%PYTHON%"
) else if exist ".venv\Scripts\python.exe" (
  set "PY=%CD%\.venv\Scripts\python.exe"
) else (
  echo [ERROR] 找不到 Python
  exit /b 1
)

echo [e2e] PY=%PY%
echo [e2e] DB=%QUIZ_DB_PATH%
"%PY%" manage.py migrate --noinput
if errorlevel 1 exit /b 1

echo [e2e] Starting Flask on http://127.0.0.1:5000
"%PY%" run_flask.py
