@echo off
echo Stopping backend service...
taskkill /F /PID 3132 2>nul
taskkill /F /PID 14612 2>nul
timeout /t 2 >nul

echo Starting backend service...
cd tabsis-backend
start "TabSIS Backend" python main.py
echo Backend service started!
pause
