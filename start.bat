@echo off
echo ==========================================
echo   Google Ads Campaign Manager
echo ==========================================
echo.

if not exist backend\.env (
  echo ERROR: backend\.env not found. Run install.bat first.
  pause
  exit /b 1
)

echo Starting Backend on http://localhost:8000...
start "Backend" cmd /c "cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo Starting Frontend on http://localhost:5173...
start "Frontend" cmd /c "cd frontend && npx vite --host 0.0.0.0"

timeout /t 3 /nobreak >nul

echo.
echo ==========================================
echo   App is running!
echo ==========================================
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo   Close the Backend and Frontend windows to stop.
echo.

start http://localhost:5173
pause
