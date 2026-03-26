#!/usr/bin/env bash
# Start both frontend and backend dev servers
# Usage: bash scripts/dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Google Ads Campaign Manager..."
echo ""

# Start backend
echo "[Backend] Starting FastAPI on http://127.0.0.1:8000"
cd "$PROJECT_ROOT/backend"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "[Frontend] Starting Vite on http://localhost:5173"
cd "$PROJECT_ROOT/frontend"
npx vite --host 127.0.0.1 &
FRONTEND_PID=$!

echo ""
echo "Both servers running. Press Ctrl+C to stop."
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://127.0.0.1:8000"
echo "  Health:   http://127.0.0.1:8000/api/health"
echo ""

# Trap Ctrl+C to kill both
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
