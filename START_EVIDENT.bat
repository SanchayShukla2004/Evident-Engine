@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Creating local Python environment...
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip show fastapi uvicorn httpx python-dotenv pydantic >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies for first run. Please wait...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
if not exist .env copy .env.example .env >nul
.venv\Scripts\python.exe run.py
exit /b 0
:failed
echo.
echo Setup failed. Confirm Python 3.10+ is installed and available as py.
pause
exit /b 1
