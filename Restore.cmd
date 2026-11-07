@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Restore.ps1"
set "STATUS=%ERRORLEVEL%"
echo.
pause
exit /b %STATUS%
