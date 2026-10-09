@echo off
setlocal
if /i "%~1"=="--worker" goto worker
"%ComSpec%" /d /k call "%~f0" --worker
exit /b
:worker
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
where py >nul 2>&1
if not errorlevel 1 (
 py -3.10 "src\start_source.py"
 if errorlevel 1 goto failed
 exit /b 0
)
where python >nul 2>&1
if not errorlevel 1 (
 python "src\start_source.py"
 if errorlevel 1 goto failed
 exit /b 0
)
echo Source mode needs Python 3.10 x64. End users can use the built FaceLocker.exe without Python.
pause
exit /b 1
:failed
echo FaceLocker could not start. Read the error above.
echo Logs: %LOCALAPPDATA%\FaceLocker\logs
pause
exit /b 1
