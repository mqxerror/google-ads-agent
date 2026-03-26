@echo off
echo ==========================================
echo   Google Ads Campaign Manager - Installer
echo ==========================================
echo.

echo [1/5] Checking prerequisites...
where node >nul 2>&1 || (echo ERROR: Node.js not found. Install from https://nodejs.org/ & exit /b 1)
where uv >nul 2>&1 || (echo ERROR: uv not found. Install from https://docs.astral.sh/uv/ & exit /b 1)
echo   Prerequisites OK

echo.
echo [2/5] Installing backend dependencies...
cd backend
uv sync
cd ..

echo.
echo [3/5] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo [4/5] Checking credentials...
if not exist backend\.env (
  copy backend\.env.example backend\.env
  echo   Created backend\.env from template.
  echo   *** EDIT backend\.env with your Google Ads API credentials ***
) else (
  echo   backend\.env exists
)

echo.
echo [5/5] Setting up data directories...
if not exist data\guidelines mkdir data\guidelines

echo.
echo ==========================================
echo   Installation complete!
echo ==========================================
echo.
echo To start the app, run: start.bat
echo.
pause
