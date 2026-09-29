@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  login.bat          -> your account (config.json, port 9251)
rem  login.bat spouse   -> config.spouse.json (own folders, profile, port)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo ============================================================
echo  Affirm - sign in
echo ============================================================
if not "%~1"=="" echo Account: %~1
echo.
echo A browser window will open on fidelity.com. Then:
echo   1. Sign in to Affirm yourself, including the text-message code.
echo   2. Open your statements or messages area if you know where it is.
echo   3. LEAVE THAT BROWSER WINDOW OPEN - do not close it.
echo   4. Then run:  paperpull affirm diagnose   (a safe look, downloads nothing)
echo.
echo READ-ONLY: this tool only downloads statements and tax forms. It NEVER
echo moves money between funds, changes contributions, withdraws, takes a
echo loan, changes beneficiaries, or changes any setting.
echo.
"%PP_PY%" affirm_docs.py --open-browser %CFG%
echo.
pause
