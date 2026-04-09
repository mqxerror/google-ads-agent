# Google Ads Campaign Manager

A local web application for managing Google Ads campaigns with an AI-powered chat agent (Claude), visual campaign browser, and per-campaign guidelines system. Includes 87 bundled Google Ads API services.

## Quick Start

### Prerequisites

- **Python** 3.12+
- **Claude Code** CLI (`npm install -g @anthropic-ai/claude-code`) — for AI chat agent
- **Google Ads API credentials** (developer token, OAuth client ID/secret, refresh token)

> **Note:** The installer automatically handles missing or outdated dependencies:
> - **Node.js** — Installed/upgraded via [nvm](https://github.com/nvm-sh/nvm) (Mac/Linux) or [winget](https://learn.microsoft.com/en-us/windows/package-manager/) (Windows) if missing or below the required version (20.19+)
> - **uv** — [uv](https://docs.astral.sh/uv/) (Python package manager) is installed automatically if not already present

### Install & Run (one command)

```bash
git clone https://github.com/mqxerror/google-ads-agent.git
cd google-ads-agent

# Install everything
bash install.sh        # Linux/Mac/Git Bash
# OR
install.bat            # Windows

# Configure credentials
# Edit backend/.env with your Google Ads API credentials

# Start the app
bash start.sh          # Linux/Mac/Git Bash
# OR
start.bat              # Windows (opens both servers + browser)
```

Open **http://localhost:5173**

## Features

- **Campaign Browser** — Account hierarchy, status filtering (Active/Paused/All), real-time metrics
- **AI Chat Agent** — Powered by Claude, with access to your Google Ads data via REST API. Can fetch search terms, analyze performance, suggest negatives, and execute changes
- **87 Bundled Google Ads Services** — Full Google Ads API coverage (campaign management, keyword planning, audience targeting, conversion tracking, bidding strategies, and more)
- **Campaign Guidelines** — Markdown-based per-campaign rules that auto-load into AI context
- **Layered Memory System** — Business context + guidelines + conversation history + session summaries + live data
- **Date Range Picker** — Day-by-day performance analysis with presets
- **Direct Operations** — Pause/enable campaigns, edit budgets, add keywords with one click
- **Search Terms Analysis** — View search terms, suggest negatives with match types
- **Model Selector** — Switch between Sonnet (fast), Opus (deep analysis), Haiku (quick/cheap)
- **Dark/Light Mode** + Cmd+K command palette

## Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI)  →  Google Ads API
     port 5173                 port 8000           (real data)
                                   ↓
                              Claude Code CLI
                              (AI chat agent)
```

- **Frontend:** React 19, TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query, react-markdown
- **Backend:** Python FastAPI, google-ads SDK v29.2.0, SQLite, 87 bundled MCP services
- **AI Agent:** Claude Code SDK, layered memory (business context + guidelines + conversation history)
- **Data:** 100% real data from Google Ads API — no mock data

## Project Structure

```
google-ads-agent/
├── install.sh / install.bat     # One-command installer
├── start.sh / start.bat         # One-command starter
├── backend/
│   ├── app/                     # FastAPI web layer
│   │   ├── main.py              # App entry point
│   │   ├── config.py            # Settings (reads .env)
│   │   ├── routers/             # REST API endpoints (31 endpoints)
│   │   ├── services/            # Agent service, Google Ads queries, guidelines
│   │   └── models/              # Pydantic schemas
│   ├── google_ads/              # Bundled MCP services (87 services)
│   │   ├── services/            # All service implementations
│   │   ├── servers/             # FastMCP tool wrappers
│   │   ├── sdk_client.py        # Google Ads SDK auth
│   │   └── mcp_main.py          # MCP server entry point
│   ├── .env                     # Your credentials (git-ignored)
│   └── .env.example             # Credential template
├── frontend/
│   └── src/
│       ├── components/          # React UI components
│       ├── lib/                 # API client, formatters
│       └── stores/              # Zustand state management
├── data/
│   ├── app.db                   # SQLite database (auto-created)
│   └── guidelines/              # Campaign guidelines .md files
└── docs/                        # PRD, Architecture, UX Design, Epics
```

## Configuration

### backend/.env

```env
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token
GOOGLE_ADS_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
GOOGLE_ADS_LOGIN_CUSTOMER_ID=your_mcc_account_id
```

### Campaign Guidelines

Place markdown files in `data/guidelines/`:
- `BUSINESS_CONTEXT.md` — Business knowledge (auto-loaded into every AI session)
- `CAMPAIGN_GUIDELINES.md` — Global rules + per-campaign sections
- Region-specific files (e.g., `MENA_CAMPAIGN_GUIDELINES.md`)

## API Endpoints

| Category | Endpoints | Description |
|----------|-----------|-------------|
| Campaigns | 7 | List accounts, campaigns, ad groups, keywords, ads, targeting |
| Operations | 6 | Pause/enable, edit budget, add/pause keywords, add negatives, search terms |
| Chat | 5 | Conversations, messages, AI agent streaming |
| Guidelines | 5 | List, read, create, update, sections |
| Setup | 3 | Credentials, status, validation |
| Health | 1 | Health check |

Full API docs at `http://localhost:8000/docs` when running.
