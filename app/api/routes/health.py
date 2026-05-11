"""Healthcheck route."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok", "service": "AI SmartEC Tickets"}
