@echo off
setlocal
if /i "%~1"=="--worker" goto worker
"%ComSpec%" /d /k call "%~f0" --worker
exit /b
:worker
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
if not exist "logs" mkdir "logs"
echo FaceLocker build started >logs\build.log
if exist ".build-env\Scripts\python.exe" (
 ".build-env\Scripts\python.exe" -c "import sys,struct; assert sys.version_info[:2]==(3,10) and struct.calcsize('P')==8" >nul 2>&1
 if errorlevel 1 (
  move ".build-env" ".build-env.previous-%RANDOM%-%RANDOM%" >nul
  if errorlevel 1 goto failed
 )
)
if not exist ".build-env\Scripts\python.exe" (
 py -3.10 -m venv .build-env >>logs\build.log 2>&1
 if errorlevel 1 goto python_error
)
echo Installing build packages. Please wait...
".build-env\Scripts\python.exe" -m pip install -r "requirements\build-requirements.txt" >>logs\build.log 2>&1
if errorlevel 1 goto failed
echo Building FaceLocker.exe. Please wait...
".build-env\Scripts\python.exe" "src\build_exe.py" >>logs\build.log 2>&1
if errorlevel 1 goto failed
echo Built: dist\FaceLocker.exe
echo Next: open dist\FaceLocker.exe to install and run the application.
echo End users run this EXE; they do not need Python or BAT files.
pause
exit /b 0
:python_error
echo Building requires Python 3.10 64-bit on Windows, with Python Launcher and Tcl/Tk.
if exist logs\build.log type logs\build.log
pause
exit /b 1
:failed
echo Build failed. See logs\build.log.
type logs\build.log
pause
exit /b 1
