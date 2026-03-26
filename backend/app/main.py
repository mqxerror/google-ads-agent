from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import campaigns, chat, guidelines, operations, setup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
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
app.include_router(campaigns.router)
app.include_router(chat.router)
app.include_router(guidelines.router)
app.include_router(operations.router)


# ── Health ──────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
