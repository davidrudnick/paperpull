@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo Resuming Discover document download.
if not "%~1"=="" echo Account: %~1
echo Make sure that account's signed-in browser is still OPEN.
"%PP_PY%" discovercard_docs.py --resume %CFG%
pause
