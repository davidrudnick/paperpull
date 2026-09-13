@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  run_all.bat          -> your account (config.json)
rem  run_all.bat spouse   -> spouse's account (config.spouse.json)
rem  Downloads the full order history. To limit it, set default_start_date
rem  in that account's config.
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo FULL Amazon download (your entire order history).
if not "%~1"=="" echo Account: %~1
echo Make sure that account's signed-in browser is still OPEN.
"%PP_PY%" amazon_receipts.py --all %CFG%
pause
