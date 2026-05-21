from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.mcp_server import mcp_lifespan
from app.routers import accounts, activity, assets, campaign_builder, campaigns, changelog, chat, guidelines, landing_page, memory, operations, outcomes, pmax, reports, search_terms, settings as settings_router, setup, skills, uploads, video
from app.services.sync_engine import start_background_sync, stop_background_sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle.

    The MCP server's lifespan must be entered here so FastMCP can bring
    up its internal StreamableHTTPSessionManager task group. Without
    this, every POST to /mcp returns 500 with 'task group not
    initialized'.
    """
    async with mcp_lifespan(app):
        await init_db()
        # Apply DB overrides to runtime settings so MCP toggles persist across restarts
        from app.routers.settings import load_settings_overrides
        await load_settings_overrides()
        start_background_sync()
        yield
        stop_background_sync()


app = FastAPI(
    title="Google Ads Campaign Manager",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────

app.include_router(setup.router)
app.include_router(accounts.router)
app.include_router(activity.router)
app.include_router(campaign_builder.router)
app.include_router(campaigns.router)
app.include_router(chat.router)
app.include_router(guidelines.router)
app.include_router(landing_page.router)
app.include_router(memory.router)
app.include_router(operations.router)
app.include_router(outcomes.router)
app.include_router(pmax.router)
app.include_router(reports.router)
app.include_router(search_terms.router)
app.include_router(skills.router)
app.include_router(settings_router.router)
app.include_router(uploads.router)
app.include_router(video.router)
app.include_router(assets.router)
app.include_router(changelog.router)


# ── MCP server (Streamable HTTP at /mcp) ────────────────────────────
# Exposes conversations/messages/personas to remote Claude Code sessions
# so the user's terminal Claude can read handoffs from the chat UI,
# execute work against production infra, and post results back into the
# thread. Auth token is logged at startup — paste it into `claude mcp add`.

from app.mcp_server import mount_mcp

_mcp_token = mount_mcp(app)
print(f"[mcp] mounted at /mcp · bearer token: {_mcp_token}", flush=True)


# ── Health ──────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
