@echo off
setlocal

echo [INFO] Adding Windows Firewall inbound rules for OnlineQuiz...
echo [INFO] Requires Administrator privileges.

netsh advfirewall firewall add rule name="OnlineQuiz Dev Frontend" dir=in action=allow protocol=TCP localport=5173
netsh advfirewall firewall add rule name="OnlineQuiz Dev Backend" dir=in action=allow protocol=TCP localport=5000
netsh advfirewall firewall add rule name="OnlineQuiz Production" dir=in action=allow protocol=TCP localport=3080

if errorlevel 1 (
  echo [ERROR] Failed. Right-click this file and choose "Run as administrator".
  exit /b 1
)

echo [OK] Firewall rules added for ports 5173, 5000, 3080.
