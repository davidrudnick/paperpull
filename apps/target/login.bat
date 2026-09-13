@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  login.bat          -> your account (config.json)
rem  login.bat spouse   -> config.spouse.json (separate folders + session)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
if not "%~1"=="" echo Account: %~1
"%PP_PY%" target_receipts.py --open-browser %CFG%
pause
