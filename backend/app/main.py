from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.mcp_server import mcp_lifespan
from app.routers import accounts, activity, assets, campaign_builder, campaigns, changelog, chat, guidelines, landing_page, memory, operations, outcomes, plans, pmax, pmax_video, reports, search_terms, settings as settings_router, setup, skills, studio, uploads, video, video_director, video_engine, workflows, youtube
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
        # Surface higgsfield CLI presence at boot so a missing npm-global
        # PATH entry fails visibly here rather than on first Studio call.
        from app.services.higgsfield_client import log_cli_presence_at_startup
        log_cli_presence_at_startup()
        # Scheduled Plans: fire due plans (incl. ones overdue from downtime).
        from app.services.scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        # Workflow runner: reap orphaned "running" zombies on boot (incl. the
        # two live-confirmed ones from the pre-decouple in-stream execution),
        # then keep sweeping periodically.
        from app.services.workflow_runner import (
            start_sweeper, stop_sweeper, sweep_zombies,
        )
        await sweep_zombies()
        start_sweeper()
        # Chat Orchestration v2: reap orphaned chat_turns on boot, then keep
        # sweeping periodically (mirrors the workflow runner's sweeper wiring).
        from app.services.chat_runner import (
            start_sweeper as start_chat_sweeper,
            stop_sweeper as stop_chat_sweeper,
            sweep_chat_zombies,
        )
        await sweep_chat_zombies()
        start_chat_sweeper()
        yield
        stop_chat_sweeper()
        stop_sweeper()
        stop_scheduler()
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
app.include_router(pmax_video.router)
app.include_router(video_engine.router)
app.include_router(youtube.router)
app.include_router(reports.router)
app.include_router(search_terms.router)
app.include_router(skills.router)
app.include_router(studio.router)
app.include_router(video_director.router)
app.include_router(settings_router.router)
app.include_router(uploads.router)
app.include_router(video.router)
app.include_router(assets.router)
app.include_router(changelog.router)
app.include_router(workflows.router)
app.include_router(workflows.account_router)   # /api/accounts/{id}/account-report (Story 13.2)
app.include_router(plans.router)


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
    """Liveness + per-account sync freshness summary (Dashboard v2.1).

    Keeps the original `{"status": "ok"}` contract and ADDS a per-account
    sync_state rollup + the age of the sync heartbeat — non-breaking.
    """
    from datetime import datetime, timezone
    from app.database import get_db

    accounts: list[dict] = []
    heartbeat_age_seconds: float | None = None
    try:
        db = await get_db()
        try:
            cur = await db.execute(
                """SELECT account_id, data_through_date, last_success_at,
                          consecutive_failures, in_progress, last_error
                   FROM sync_state WHERE domain = 'metrics'"""
            )
            for r in await cur.fetchall():
                if r["in_progress"]:
                    state = "syncing"
                elif r["consecutive_failures"] or r["last_error"]:
                    state = "error"
                elif r["last_success_at"]:
                    state = "ok"
                else:
                    state = "stale"
                accounts.append({
                    "account_id": r["account_id"],
                    "state": state,
                    "data_through_date": r["data_through_date"],
                    "last_success_at": r["last_success_at"],
                    "consecutive_failures": int(r["consecutive_failures"] or 0),
                })
            cur = await db.execute(
                "SELECT value FROM config WHERE key = 'sync_heartbeat'"
            )
            hb_row = await cur.fetchone()
        finally:
            await db.close()
        if hb_row and hb_row["value"]:
            try:
                hb = datetime.fromisoformat(hb_row["value"])
                if hb.tzinfo is None:
                    hb = hb.replace(tzinfo=timezone.utc)
                heartbeat_age_seconds = round(
                    (datetime.now(timezone.utc) - hb).total_seconds(), 1
                )
            except (ValueError, TypeError):
                pass
    except Exception:
        # Health must never 500 — degrade to the liveness contract.
        pass

    return {
        "status": "ok",
        "sync": accounts,
        "heartbeat_age_seconds": heartbeat_age_seconds,
    }


# ── Built frontend (always-on app at :8000) ─────────────────────────
# The Vite dev server (:5173) is session-tied and kept dying mid-work,
# taking "the app" down with it. The backend runs as a launchd service
# and never dies — so it also serves the production build from
# frontend/dist. Use http://localhost:8000 for the always-on app;
# :5173 remains a dev-only HMR convenience. Rebuild with
# `cd frontend && npx vite build` after frontend changes.

from fastapi.responses import FileResponse  # noqa: E402

_FRONTEND_DIST = settings.PROJECT_ROOT.parent / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Serve the built SPA: real files as-is, everything else falls back to
    index.html so client-side routes (/c/:id, /studio) deep-link correctly.
    Registered LAST so /api/* routers and the /mcp mount keep priority."""
    if not _FRONTEND_DIST.exists():
        return {"detail": "frontend build missing — run: cd frontend && npx vite build"}
    candidate = (_FRONTEND_DIST / full_path).resolve()
    # Path-traversal guard + only serve real files inside dist
    if (
        full_path
        and str(candidate).startswith(str(_FRONTEND_DIST.resolve()))
        and candidate.is_file()
    ):
        return FileResponse(candidate)
    return FileResponse(_FRONTEND_DIST / "index.html")
