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

# Minimum Node.js version required (major.minor)
REQUIRED_NODE_MAJOR=20
REQUIRED_NODE_MINOR=19

# Load nvm if available (needed for nvm-managed Node installs)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

install_or_upgrade_node() {
  echo "  Installing nvm and Node.js >= $REQUIRED_NODE_MAJOR.$REQUIRED_NODE_MINOR..."
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  fi
  nvm install "$REQUIRED_NODE_MAJOR"
  nvm use --delete-prefix "$REQUIRED_NODE_MAJOR" 2>/dev/null || nvm use "$REQUIRED_NODE_MAJOR"
}

if ! command -v node &>/dev/null; then
  echo "  Node.js not found — installing automatically..."
  install_or_upgrade_node
  if ! command -v node &>/dev/null; then
    echo "ERROR: Failed to install Node.js. Install manually from https://nodejs.org/"
    exit 1
  fi
  echo "  Node.js: $(node --version) (just installed)"
else
  # Check if Node.js version meets minimum requirement
  NODE_VERSION=$(node --version | sed 's/^v//')
  NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
  NODE_MINOR=$(echo "$NODE_VERSION" | cut -d. -f2)
  if [ "$NODE_MAJOR" -lt "$REQUIRED_NODE_MAJOR" ] || \
     { [ "$NODE_MAJOR" -eq "$REQUIRED_NODE_MAJOR" ] && [ "$NODE_MINOR" -lt "$REQUIRED_NODE_MINOR" ]; }; then
    echo "  Node.js $(node --version) is too old (need >= $REQUIRED_NODE_MAJOR.$REQUIRED_NODE_MINOR) — upgrading..."
    install_or_upgrade_node
    echo "  Node.js: $(node --version) (upgraded)"
  else
    echo "  Node.js: $(node --version)"
  fi
fi

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found."
  exit 1
fi
echo "  npm: $(npm --version)"

if ! command -v uv &>/dev/null; then
  echo "  uv not found — installing automatically..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Source the updated PATH so uv is available in this session
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv &>/dev/null; then
    echo "ERROR: Failed to install uv. Install manually from https://docs.astral.sh/uv/"
    exit 1
  fi
  echo "  uv: $(uv --version) (just installed)"
else
  echo "  uv: $(uv --version)"
fi

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
