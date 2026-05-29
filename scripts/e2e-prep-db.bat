@echo off
setlocal
cd /d "%~dp0..\backend"
set "QUIZ_DB_PATH=%~dp0..\data\e2e-quiz.db"
if exist "%QUIZ_DB_PATH%" del /f /q "%QUIZ_DB_PATH%" 2>nul
if exist "%QUIZ_DB_PATH%-wal" del /f /q "%QUIZ_DB_PATH%-wal" 2>nul
if exist "%QUIZ_DB_PATH%-shm" del /f /q "%QUIZ_DB_PATH%-shm" 2>nul
if defined PYTHON (set "PY=%PYTHON%") else (set "PY=%CD%\.venv\Scripts\python.exe")
"%PY%" manage.py migrate --noinput
