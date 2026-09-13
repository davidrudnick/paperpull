@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo Read-only inspection of the UKG documents page. Downloads NOTHING.
if not "%~1"=="" echo Account: %~1
echo Make sure you are signed in and your documents page is open.
"%PP_PY%" ukg_docs.py --diagnose %CFG%
pause
