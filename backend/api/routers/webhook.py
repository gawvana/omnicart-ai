"""
OmniCart AI — Telegram Webhook Router.
Handles Telegram Bot API webhooks with secret token verification and update idempotency.
"""

from __future__ import annotations

import collections
import hmac
import logging
from typing import Annotated, Any, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from api.deps import get_db, get_dispatcher, get_redis_client
from core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telegram Webhook"])

# In-memory LRU cache for update_id deduplication fallback when Redis is absent
_SEEN_UPDATES: collections.deque[int] = collections.deque(maxlen=10000)
_SEEN_UPDATES_SET: set[int] = set()


def _is_duplicate_local(update_id: int) -> bool:
    if update_id in _SEEN_UPDATES_SET:
        return True
    if len(_SEEN_UPDATES) >= 10000:
        oldest = _SEEN_UPDATES.popleft()
        _SEEN_UPDATES_SET.discard(oldest)
    _SEEN_UPDATES.append(update_id)
    _SEEN_UPDATES_SET.add(update_id)
    return False


async def is_duplicate_update(update_id: int, r: aioredis.Redis | None) -> bool:
    """Check if update_id was already delivered to guarantee idempotency."""
    if r is not None:
        try:
            # Set key only if not exists, 2 hour expiration
            key = f"tg_update:{update_id}"
            acquired = await r.set(key, "1", nx=True, ex=7200)
            return acquired is None
        except Exception as exc:
            logger.warning("Redis update idempotency check failed: %s", exc)
    return _is_duplicate_local(update_id)


async def _process_telegram_update(body: dict[str, Any]) -> None:
    settings = get_settings()
    dp = get_dispatcher()

    async with Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    ) as bot:
        try:
            from api.deps import _session_factory, _init_resources
            session_factory = _session_factory
            if session_factory is None:
                await _init_resources()
                from api.deps import _session_factory as updated_factory
                session_factory = updated_factory

            if session_factory:
                async with session_factory() as db:
                    update = Update.model_validate(body, context={"bot": bot})
                    await dp.feed_update(bot=bot, update=update, db_session=db)
            else:
                logger.error("No DB session factory available for update processing")
        except Exception as exc:
            logger.exception("Error processing Telegram update: %s", exc)


@router.get("/api/webhook")
@router.get("/api/webhook.py")
@router.get("/webhook")
async def telegram_webhook_info() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "OmniCart AI Telegram Webhook is active and waiting for POST updates",
    }


@router.post("/api/webhook")
@router.post("/api/webhook.py")
@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    r: Annotated[Optional[aioredis.Redis], Depends(get_redis_client)],
    secret_token: Annotated[Optional[str], Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, Any]:
    """
    Direct Telegram Bot Webhook endpoint.
    - Constant-time secret token validation
    - Idempotency deduplication using update_id
    - Direct await so Vercel Serverless executes before lambda termination
    """
    settings = get_settings()
    if settings.telegram_webhook_secret:
        if not secret_token or not hmac.compare_digest(secret_token, settings.telegram_webhook_secret):
            raise HTTPException(status_code=403, detail="Invalid webhook secret token")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}")

    # Idempotency check
    update_id = body.get("update_id")
    if update_id is not None:
        try:
            update_id_int = int(update_id)
            if await is_duplicate_update(update_id_int, r):
                logger.info("Ignoring duplicate Telegram update %d", update_id_int)
                return {"ok": True, "duplicate": True}
        except (ValueError, TypeError):
            pass

    try:
        await _process_telegram_update(body)
    except Exception as exc:
        logger.exception("Error executing Telegram update: %s", exc)

    return {"ok": True}


@router.get("/api/v1/bot/setup-webhook")
@router.post("/api/v1/bot/setup-webhook")
async def setup_bot_webhook(
    webhook_url: Optional[str] = Query(None, description="Full webhook URL e.g. https://domain.vercel.app/api/webhook"),
) -> dict[str, Any]:
    """Helper endpoint to register webhook with Telegram Bot API."""
    settings = get_settings()
    url = webhook_url or f"{settings.telegram_webapp_url.rstrip('/')}/api/webhook"
    secret = settings.telegram_webhook_secret or None

    async with Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    ) as bot:
        await bot.set_webhook(
            url=url,
            secret_token=secret,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
        webhook_info = await bot.get_webhook_info()
        return {
            "status": "webhook_configured",
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
        }
