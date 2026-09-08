"""
OmniCart AI — Health & Scheduled Jobs (Cron) Router.
Monitors system vitality and runs serverless scheduled replenishment and analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get("/api/health")
@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint indicating server and subsystem availability."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "OmniCart AI",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "serverless": settings.is_serverless,
        "database_configured": bool(settings.database_url),
        "redis_configured": bool(settings.redis_url),
    }


@router.get("/api/cron")
@router.post("/api/cron")
async def cron_trigger(request: Request) -> dict[str, Any]:
    """Vercel Cron endpoint to run scheduled replenishment intervals."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization", "")

    if settings.cron_secret:
        expected = f"Bearer {settings.cron_secret}"
        if auth_header != expected:
            raise HTTPException(status_code=401, detail="Unauthorized cron trigger")

    from api.deps import _init_resources, _session_factory
    if _session_factory is None:
        await _init_resources()
        from api.deps import _session_factory as updated_factory
        _session_factory = updated_factory

    from services.worker import compute_replenishment_intervals, update_price_index_from_purchases

    ctx = {"session_factory": _session_factory}
    intervals_updated = await compute_replenishment_intervals(ctx)
    prices_updated = await update_price_index_from_purchases(ctx)

    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "replenishment_intervals_updated": intervals_updated,
        "price_indexes_processed": prices_updated,
    }
