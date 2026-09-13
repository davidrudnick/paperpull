@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  run_all.bat        -> your account (config.json)
rem  run_all.bat jane   -> config.jane.json (separate folders + progress)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo FULL account-wide download (Online + In-store).
if not "%~1"=="" echo Account: %~1
echo Make sure that account's signed-in browser is still OPEN.
"%PP_PY%" walmart_receipts.py --all %CFG%
pause
