@echo off
setlocal
if /i "%~1"=="--worker" goto worker
"%ComSpec%" /d /k call "%~f0" --worker
exit /b
:worker
cd /d "%~dp0.."
set "FACELOCKER_HOME=%LOCALAPPDATA%\FaceLocker"
set "TCL_LIBRARY="
set "TK_LIBRARY="
set "TCLLIBPATH="
set "PYTHONHOME="
set "PYTHONPATH="
set "FACELOCKER_READY_FILE="
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
if not exist "%FACELOCKER_HOME%\logs" mkdir "%FACELOCKER_HOME%\logs"
if not exist "%FACELOCKER_HOME%\.venv\Scripts\python.exe" goto missing
if not exist "%FACELOCKER_HOME%\app\app.py" goto missing
echo Starting the installed app directly. Close existing FaceLocker processes first.
echo Your installed face database and settings will be used.
"%FACELOCKER_HOME%\.venv\Scripts\python.exe" -u -X faulthandler "src\runtime_entry.py" --installed >"%FACELOCKER_HOME%\logs\diagnostic.log" 2>&1
set "FACELOCKER_DIAG_EXIT=%ERRORLEVEL%"
echo Application exit code: %FACELOCKER_DIAG_EXIT%
type "%FACELOCKER_HOME%\logs\diagnostic.log"
echo Send diagnostic.log if no window appeared.
pause
exit /b %FACELOCKER_DIAG_EXIT%
:missing
echo Installed app not found. Run dist\FaceLocker.exe once first.
pause
exit /b 1
