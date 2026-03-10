from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router
from app.routers.repos import router as repos_router
from app.routers.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup
    print(f"🚀 {settings.APP_NAME} starting in {settings.ENVIRONMENT} mode")
    yield
    # Shutdown
    print(f"👋 {settings.APP_NAME} shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description="Open Source Evolution Explorer — visualize repository history, "
    "contributor networks, and ecosystem dependencies.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS Middleware ────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───────────────────────────────────────────────
app.include_router(health_router)
app.include_router(repos_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }
