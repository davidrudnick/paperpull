@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  login.bat          -> your account (config.json, port 9230)
rem  login.bat spouse   -> config.spouse.json (own folders, profile, port)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo ============================================================
echo  Verizon Documents - sign in
echo ============================================================
if not "%~1"=="" echo Account: %~1
echo.
echo A normal Chromium window will open. Then:
echo   1. Sign in to Verizon (do all the 2FA / device approval yourself).
echo   2. Go to Account -^> Reports ^& statements (Documents / Tax center).
echo   3. LEAVE THAT BROWSER WINDOW OPEN - do not close it.
echo   4. Then run:  diagnose.bat %~1   (a safe look, downloads nothing)
echo.
echo READ-ONLY: this tool only downloads statements and tax documents.
echo It NEVER buys, sells, trades, transfers, withdraws, moves crypto, or
echo changes any setting.
echo.
"%PP_PY%" verizon_docs.py --open-browser %CFG%
echo.
pause
