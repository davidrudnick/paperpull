@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  run_pilot.bat spouse  -> pilots spouse's account
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo Pilot: 5 newest statements/tax documents, then STOPS.
if not "%~1"=="" echo Account: %~1
echo Make sure that account's signed-in browser is still OPEN.
"%PP_PY%" wealthfront_docs.py --pilot %CFG%
pause
