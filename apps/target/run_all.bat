@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  run_all.bat          -> your account
rem  run_all.bat spouse   -> spouse's account (separate folders + progress)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo FULL account-wide download (Online + In-store).
if not "%~1"=="" echo Account: %~1
echo Run the pilot first if you have not: run_pilot.bat %~1
"%PP_PY%" target_receipts.py --all %CFG%
pause
