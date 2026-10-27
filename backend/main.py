"""FastAPI application entry point for Mnemos.

Run from the repository root:
    uvicorn backend.main:app --reload
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db
from backend.routers.auth import router as auth_router
from backend.routers.chat import router as chat_router
from backend.routers.memories import router as memories_router

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
logger = logging.getLogger("mnemos")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    # MVP bootstrap: create SQLite tables when the API starts.
    init_db()
    if not settings.has_nebius_key:
        logger.warning(
            "Nebius API key is not configured. Add NEBIUS_TOKEN_FACTORY_KEY "
            "to the environment before chatting."
        )
    if not settings.has_tavily_key:
        logger.info("TAVILY_API_KEY is not configured; live web research will be skipped.")
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A personal research assistant with persistent memory and live web research.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}


@app.get("/health", tags=["system"])
def health() -> dict[str, str | bool]:
    """Health/status endpoint; does not make a billable model request."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "nebius_configured": settings.has_nebius_key,
        "tavily_configured": settings.has_tavily_key,
    }


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(memories_router)
