@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  Date cutoff comes from each account's config (default_start_date).
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo Resuming Amazon download.
if not "%~1"=="" echo Account: %~1
echo Make sure that account's signed-in browser is still OPEN.
"%PP_PY%" amazon_receipts.py --resume %CFG%
pause
