"""Dawae-Check FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.db.session import Base, engine

logger = logging.getLogger("dawae-check")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting Dawae-Check backend …")
    logger.info("DATABASE_URL = %s", settings.DATABASE_URL.split("@")[-1])
    logger.info("MOCK_AI_ENGINE = %s", settings.MOCK_AI_ENGINE)

    # Import models so metadata is populated
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured (create_all).")

    yield

    await engine.dispose()
    logger.info("Engine disposed. Shutdown complete.")


app = FastAPI(
    title="Dawae-Check API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Wire routers ────────────────────────────────────────────────────────────
from app.api.v1.health import router as health_router  # noqa: E402
from app.api.v1.verify import router as verify_router  # noqa: E402
from app.api.v1.batches import router as batches_router  # noqa: E402
from app.api.v1.scans import router as scans_router  # noqa: E402

app.include_router(health_router, prefix="/api/v1")
app.include_router(verify_router, prefix="/api/v1")
app.include_router(batches_router, prefix="/api/v1")
app.include_router(scans_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok"}
