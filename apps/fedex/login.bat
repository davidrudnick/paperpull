@echo off
cd /d "%~dp0"
set "PP_PY=.venv\Scripts\python.exe"
if exist "..\..\.venv\Scripts\python.exe" set "PP_PY=..\..\.venv\Scripts\python.exe"
rem  login.bat          -> your account (config.json, port 9278)
rem  login.bat spouse   -> config.spouse.json (own folders, profile, port)
if "%~1"=="" (set "CFG=") else (set "CFG=--config config.%~1.json")
echo ============================================================
echo  FedEx Documents - sign in
echo ============================================================
if not "%~1"=="" echo Account: %~1
echo.
echo Your own Edge or Chrome will open, with a separate profile. Then:
echo   1. Sign in to fedex.com yourself, including any code it sends.
echo   2. LEAVE THAT BROWSER WINDOW OPEN - do not close it.
echo   3. Then run:  paperpull fedex pilot   (the five newest documents)
echo.
echo READ-ONLY: this tool only downloads your FedEx invoice PDFs. It NEVER
echo pays, disputes, connects an account, or changes any setting.
echo.
"%PP_PY%" fedex_docs.py --open-browser %CFG%
echo.
pause
