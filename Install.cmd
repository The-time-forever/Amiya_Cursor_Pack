@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo   AMIYA CHIBI CURSOR PACK - INSTALLER
 echo =============================================
echo Installing the multi-resolution cursor scheme...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Install.ps1"
set "STATUS=%ERRORLEVEL%"
echo.
if not "%STATUS%"=="0" echo Installation failed, see error above.
if "%STATUS%"=="0" echo Finished. Check Windows Mouse Properties - Pointers.
pause
exit /b %STATUS%
