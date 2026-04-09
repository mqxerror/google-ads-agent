from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import accounts, campaigns, chat, guidelines, operations, search_terms, settings as settings_router, setup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    # Apply DB overrides to runtime settings so MCP toggles persist across restarts
    from app.routers.settings import load_settings_overrides
    await load_settings_overrides()
    yield


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
app.include_router(campaigns.router)
app.include_router(chat.router)
app.include_router(guidelines.router)
app.include_router(operations.router)
app.include_router(search_terms.router)
app.include_router(settings_router.router)


# ── Health ──────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
