@echo off
echo ==========================================
echo   Google Ads Campaign Manager - Installer
echo ==========================================
echo.

echo [1/5] Checking prerequisites...

:: Check Node.js — install via winget if missing or too old
set NODE_OK=0
where node >nul 2>&1
if %errorlevel% neq 0 (
  echo   Node.js not found — installing automatically...
  winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements >nul 2>&1
  set "PATH=%ProgramFiles%\nodejs;%PATH%"
  where node >nul 2>&1 || (echo ERROR: Failed to install Node.js. Install manually from https://nodejs.org/ & exit /b 1)
  echo   Node.js installed successfully
  set NODE_OK=1
)
if %NODE_OK%==0 (
  for /f "tokens=1,2 delims=." %%a in ('node -v') do (
    set "NODE_VER=%%a"
    set "NODE_MINOR=%%b"
  )
  set "NODE_VER=%NODE_VER:~1%"
  :: Require Node >= 20.19
  if %NODE_VER% LSS 20 (
    echo   Node.js too old — upgrading...
    winget upgrade OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements >nul 2>&1
    echo   Node.js upgraded
  ) else if %NODE_VER%==20 if %NODE_MINOR% LSS 19 (
    echo   Node.js too old — upgrading...
    winget upgrade OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements >nul 2>&1
    echo   Node.js upgraded
  )
)
echo   Node.js: && node -v

where uv >nul 2>&1
if %errorlevel% neq 0 (
  echo   uv not found — installing automatically...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  where uv >nul 2>&1 || (echo ERROR: Failed to install uv. Install manually from https://docs.astral.sh/uv/ & exit /b 1)
  echo   uv installed successfully
)
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
