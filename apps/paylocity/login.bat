@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  login.bat          -> your account (config.json, port 9239)
rem  login.bat spouse   -> config.spouse.json (own folders, profile, port)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo ============================================================
echo  Paylocity Pay Statements - sign in
echo ============================================================
if not "%~1"=="" echo Account: %~1
echo.
echo A normal browser window opens at access.paylocity.com. Then:
echo   1. Sign in the way your company does - a Paylocity username and password,
echo      or your company's single sign-on. Either is fine: this tool never
echo      sees your credentials and never touches the sign-in itself.
echo   2. Complete any MFA / verification prompt yourself.
echo   3. Open your Pay / Pay Statements area and confirm you can see them.
echo   4. LEAVE THAT BROWSER WINDOW OPEN - do not close it.
echo.
"%PP_PY%" paylocity_docs.py --open-browser %CFG%
echo.
pause
