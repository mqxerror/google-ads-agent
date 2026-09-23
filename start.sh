#!/usr/bin/env bash
# Google Ads Campaign Manager — Start both servers
# Usage: bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load nvm if available (needed for nvm-managed Node installs)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Ensure uv is on PATH
export PATH="$HOME/.local/bin:$PATH"

echo "=========================================="
echo "  Google Ads Campaign Manager"
echo "=========================================="
echo ""

# Check .env
if [ ! -f "$SCRIPT_DIR/backend/.env" ] || ! grep -q "GOOGLE_ADS_DEVELOPER_TOKEN=." "$SCRIPT_DIR/backend/.env" 2>/dev/null; then
  echo "ERROR: backend/.env is missing or not configured."
  echo "Run: bash install.sh"
  exit 1
fi

# Start backend
echo "[Backend] Starting on http://localhost:8000"
cd "$SCRIPT_DIR/backend"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
echo "[Backend] Waiting for startup..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "[Backend] Ready!"
    break
  fi
  sleep 1
done

# Start frontend
echo "[Frontend] Starting on http://localhost:5173"
cd "$SCRIPT_DIR/frontend"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "  App is running!"
echo "=========================================="
echo ""
echo "  Frontend:  http://localhost:5173"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Trap Ctrl+C to kill both
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
