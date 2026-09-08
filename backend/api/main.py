"""
OmniCart AI — Modular FastAPI Application.
Coordinates modular API routers, lifespan resource initialization, and security policies.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from api.deps import _background_tasks, _bai_client, _engine, _init_resources, _redis
from api.routers import ai, cart, checklist, health, user, webhook
from core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager initializing DB, Redis, and webhook."""
    await _init_resources()
    settings = get_settings()

    # Automatically configure Telegram Webhook during lifespan startup if token & url configured
    if settings.telegram_bot_token and settings.telegram_webapp_url:
        try:
            webhook_url = f"{settings.telegram_webapp_url.rstrip('/')}/api/webhook"
            secret = settings.telegram_webhook_secret or None
            async with Bot(
                token=settings.telegram_bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            ) as b:
                await b.set_webhook(
                    url=webhook_url,
                    secret_token=secret,
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=True,
                )
                logger.info("Lifespan: Telegram webhook configured for %s", webhook_url)
        except Exception as exc:
            logger.warning("Lifespan: Could not automatically configure Telegram webhook: %s", exc)

    logger.info("OmniCart AI API started — DB, Redis, B.AI ready")
    yield

    # Graceful shutdown of background tasks and connections
    if _background_tasks:
        for t in list(_background_tasks):
            if not t.done():
                t.cancel()

    if _bai_client and _bai_client._client:
        await _bai_client._client.aclose()
    if _redis:
        await _redis.aclose()
    if _engine:
        await _engine.dispose()

    logger.info("OmniCart AI API shut down cleanly")


# Settings & App instance
settings = get_settings()

app = FastAPI(
    title="OmniCart AI",
    version="2.0.0",
    description="Smart Grocery Shopping & Family Cart Synchronization Platform",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# CORS setup
_cors_origins_raw = os.environ.get("ALLOWED_ORIGINS", "https://localhost")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# Include Routers
app.include_router(checklist.router)
app.include_router(cart.router)
app.include_router(ai.router)
app.include_router(webhook.router)
app.include_router(health.router)
app.include_router(user.router)


# Error Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    error_msg = str(exc) if settings.debug else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={
            "error": error_msg,
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )
