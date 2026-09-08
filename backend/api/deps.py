"""
OmniCart AI — API Dependencies & Shared Infrastructure.
Manages database sessions, Redis rate-limiting, and Telegram initData verification.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
import time
import uuid
from decimal import Decimal
from typing import Annotated, Any, AsyncGenerator, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import get_settings
from core.security import (
    SecurityValidationError,
    TelegramSecurityValidator,
    TelegramUser,
    ValidatedInitData,
)
from database.models import (
    Base,
    PurchaseHistory,
    User,
    UserSettings,
    hash_telegram_id,
)
from services.b_ai_client import BAIClient, BAIClientError

logger = logging.getLogger(__name__)

# Global resource holders
_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis: aioredis.Redis | None = None
_bai_client: BAIClient | None = None
_dp: Dispatcher | None = None
_background_tasks: set[asyncio.Task[Any]] = set()


def track_task(coro: Any) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def _init_resources() -> None:
    global _engine, _session_factory, _redis, _bai_client
    settings = get_settings()

    if _engine is None and settings.database_url:
        try:
            if settings.is_serverless:
                _engine = create_async_engine(
                    settings.database_url,
                    echo=settings.debug,
                    poolclass=NullPool,
                )
            else:
                _engine = create_async_engine(
                    settings.database_url,
                    echo=settings.debug,
                    pool_size=10,
                    max_overflow=5,
                    pool_pre_ping=True,
                    pool_recycle=1800,
                )
            _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.warning("Database initialization warning: %s", exc)

    if _redis is None and settings.redis_url:
        try:
            _redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10 if settings.is_serverless else 50,
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
            )
            await _redis.ping()
        except Exception as exc:
            logger.warning("Redis unreachable (%s), running in fallback mode", exc)
            _redis = None

    if _bai_client is None and settings.bai_api_key:
        _bai_client = BAIClient(settings)
        _bai_client._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=3.0,
                read=settings.http_client_read_timeout_seconds,
                write=3.0,
                pool=3.0,
            ),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )


def get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        _dp = Dispatcher()
        from bot.handlers.start import router as start_router
        _dp.include_router(start_router)
    return _dp


def _sanitize_string(value: str) -> str:
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return cleaned[:5000]


def verify_telegram_init_data(init_data: str, bot_token: str) -> TelegramUser:
    settings = get_settings()
    validator = TelegramSecurityValidator(
        bot_token,
        max_auth_age_seconds=settings.telegram_initdata_max_age_seconds,
    )
    try:
        validated: ValidatedInitData = validator.validate_init_data(init_data)
        return validated.user
    except SecurityValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        await _init_resources()
    if _session_factory is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    async with _session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis_client() -> aioredis.Redis | None:
    if _redis is None:
        await _init_resources()
    return _redis


async def get_bai() -> BAIClient:
    if _bai_client is None:
        await _init_resources()
    if _bai_client is None:
        raise HTTPException(status_code=503, detail="B.AI client not initialized")
    return _bai_client


async def verify_and_rate_limit(
    request: Request,
    r: Annotated[aioredis.Redis | None, Depends(get_redis_client)],
) -> TelegramUser:
    cfg = get_settings()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("tma "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'tma '",
        )

    init_data = auth_header[4:]
    tg_user = verify_telegram_init_data(init_data, cfg.telegram_bot_token)

    if r is not None:
        try:
            rate_key = f"rate:{tg_user.id}"
            now = time.time()
            window = 60.0

            pipe = r.pipeline()
            pipe.zremrangebyscore(rate_key, 0, now - window)
            pipe.zadd(rate_key, {str(now): now})
            pipe.zcard(rate_key)
            pipe.expire(rate_key, int(window) + 1)
            results = await pipe.execute()

            request_count: int = results[2]
            if request_count > cfg.rate_limit_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({cfg.rate_limit_per_minute}/min)",
                    headers={"Retry-After": "60"},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Rate limiter Redis failure: %s", exc)

    return tg_user


AuthUser = Annotated[TelegramUser, Depends(verify_and_rate_limit)]
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_or_create_user(tg_user: TelegramUser, db: AsyncSession) -> User:
    id_hash = hash_telegram_id(tg_user.id)
    result = await db.execute(
        select(User).where(User.telegram_id_hash == id_hash)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user_uuid = uuid.uuid4()
        user = User(
            id=user_uuid,
            telegram_id_hash=id_hash,
            username=tg_user.username[:255] if tg_user.username else None,
            first_name=tg_user.first_name[:255] if tg_user.first_name else None,
            language_code=tg_user.language_code[:10] if tg_user.language_code else "en",
        )
        db.add(user)
        user_settings = UserSettings(id=uuid.uuid4(), user_id=user_uuid)
        db.add(user_settings)
        await db.commit()
        await db.refresh(user)
        logger.info("Created new user %s", user.id)

    return user
