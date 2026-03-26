#!/usr/bin/env bash
# Google Ads Campaign Manager — One-command installer
# Usage: bash install.sh

set -e

echo "=========================================="
echo "  Google Ads Campaign Manager - Installer"
echo "=========================================="
echo ""

# Check prerequisites
echo "[1/5] Checking prerequisites..."

if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install from https://nodejs.org/"
  exit 1
fi
echo "  Node.js: $(node --version)"

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found."
  exit 1
fi
echo "  npm: $(npm --version)"

if ! command -v uv &>/dev/null; then
  echo "ERROR: uv not found. Install from https://docs.astral.sh/uv/"
  exit 1
fi
echo "  uv: $(uv --version)"

if ! command -v claude &>/dev/null; then
  echo "WARNING: Claude Code CLI not found. AI chat will not work."
  echo "  Install with: npm install -g @anthropic-ai/claude-code"
else
  echo "  Claude Code: $(claude --version 2>/dev/null || echo 'installed')"
fi

# Install backend dependencies
echo ""
echo "[2/5] Installing backend dependencies..."
cd backend
uv sync
cd ..

# Install frontend dependencies
echo ""
echo "[3/5] Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Check .env
echo ""
echo "[4/5] Checking credentials..."
if [ ! -f backend/.env ]; then
  echo "  No backend/.env found. Creating from template..."
  cp backend/.env.example backend/.env
  echo ""
  echo "  *** IMPORTANT ***"
  echo "  Edit backend/.env with your Google Ads API credentials:"
  echo "    GOOGLE_ADS_DEVELOPER_TOKEN=your_token"
  echo "    GOOGLE_ADS_CLIENT_ID=your_client_id"
  echo "    GOOGLE_ADS_CLIENT_SECRET=your_secret"
  echo "    GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token"
  echo "    GOOGLE_ADS_LOGIN_CUSTOMER_ID=your_mcc_id"
  echo ""
else
  echo "  backend/.env exists"
fi

# Create data directories
echo ""
echo "[5/5] Setting up data directories..."
mkdir -p data/guidelines

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "To start the app, run:"
echo "  bash start.sh"
echo ""
