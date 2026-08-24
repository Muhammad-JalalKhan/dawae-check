"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness probe for deployment health checks."""
    return {"status": "healthy", "version": "0.1.0"}
