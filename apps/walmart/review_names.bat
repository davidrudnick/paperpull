@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
if not "%~1"=="" echo Account: %~1
"%PP_PY%" walmart_receipts.py --review-names %CFG%
pause
