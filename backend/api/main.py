"""
OmniCart AI — FastAPI application.

Security layers:
- HMAC-SHA256 cryptographic verification of Telegram initData on every request
- Sliding-window rate limiting via Redis
- CORS restriction to configured origins
- Input sanitization middleware
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, AsyncGenerator, Optional
from urllib.parse import parse_qs, unquote

import httpx

import redis.asyncio as aioredis
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from core.config import get_settings
from database.models import (
    Base,
    LocalPriceIndex,
    PurchaseHistory,
    User,
    UserSettings,
    hash_telegram_id,
)
from services.b_ai_client import BAIClient, BAIClientError
from services.cron_parser import PriceCronService
from services.universal_ai_parser import UniversalAIParser

logger = logging.getLogger(__name__)


# ── Lifespan & Resources ─────────────────────────────────────────────────────

_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis: aioredis.Redis | None = None
_bai_client: BAIClient | None = None
_bot: Bot | None = None
_dp: Dispatcher | None = None


async def _init_resources() -> None:
    """Initialize DB engine, session factory, Redis, and B.AI lazily or during lifespan."""
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

            # Auto create tables on initial connect
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
            logger.warning("Redis not reachable (%s), rate limiter running in fallback mode", exc)
            _redis = None

    if _bai_client is None and settings.bai_api_key:
        _bai_client = BAIClient(settings)
        _bai_client._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )


def get_dispatcher() -> Dispatcher:
    """Get or initialize singleton Dispatcher."""
    global _dp
    if _dp is None:
        _dp = Dispatcher()
        from bot.handlers.start import router as start_router
        _dp.include_router(start_router)
    return _dp


def get_bot_dispatcher() -> tuple[Bot, Dispatcher]:
    """Get or initialize Bot and Dispatcher."""
    settings = get_settings()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    return bot, get_dispatcher()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _init_resources()
    logger.info("OmniCart AI API started — DB, Redis, B.AI ready")
    yield

    if _bai_client and _bai_client._client:
        await _bai_client._client.aclose()
    if _redis:
        await _redis.aclose()
    if _engine:
        await _engine.dispose()
    if _bot:
        await _bot.session.close()

    logger.info("OmniCart AI API shut down cleanly")



# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OmniCart AI",
    version="1.0.0",
    description="Smart Grocery Shopping & Local Market Analytics Platform",
    lifespan=lifespan,
)

# CORS must be registered at module level (before ASGI stack is built).
# Read directly from env to avoid full Settings validation at import time.
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


# ── Telegram initData Verification ──────────────────────────────────────────


class TelegramUser(BaseModel):
    """Decoded Telegram user from initData."""

    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = "en"


def verify_telegram_init_data(init_data: str, bot_token: str) -> TelegramUser:
    """
    Cryptographically verify Telegram WebApp initData using HMAC-SHA256.

    Algorithm (per Telegram docs):
    1. Parse the query string into key=value pairs.
    2. Remove the `hash` parameter and sort remaining pairs alphabetically.
    3. Build a data-check-string by joining with newlines.
    4. Compute HMAC-SHA256(secret_key, data_check_string) where
       secret_key = HMAC-SHA256("WebAppData", bot_token).
    5. Compare the computed hash with the received hash.
    """
    parsed = parse_qs(init_data, keep_blank_values=True)

    received_hash = parsed.pop("hash", [None])[0]
    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    # Sort key=value pairs alphabetically and build check string
    data_check_pairs: list[str] = []
    for key in sorted(parsed.keys()):
        values = parsed[key]
        value = values[0] if values else ""
        data_check_pairs.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_pairs)

    # Compute secret key: HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # Compute expected hash: HMAC-SHA256(secret_key, data_check_string)
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData signature",
        )

    # Extract user object
    user_raw = parsed.get("user", [None])[0]
    if not user_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user in initData",
        )

    try:
        user_data = json.loads(unquote(user_raw))
        return TelegramUser(**user_data)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user data in initData: {exc}",
        ) from exc


# ── Dependencies ─────────────────────────────────────────────────────────────


def _sanitize_string(value: str) -> str:
    """Remove null bytes, control characters, and limit length."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return cleaned[:5000]


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
    """
    Combined dependency:
    1. Extract & verify Telegram initData from Authorization header
    2. Apply sliding-window rate limiting per user (if Redis is available)
    """
    cfg = get_settings()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("tma "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'tma '",
        )

    init_data = auth_header[4:]
    tg_user = verify_telegram_init_data(init_data, cfg.telegram_bot_token)

    # Sliding window rate limiting
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


# ── Helper: Get or create user ───────────────────────────────────────────────


async def get_or_create_user(
    tg_user: TelegramUser, db: AsyncSession
) -> User:
    """Fetch existing user by hashed Telegram ID or create a new one."""
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


# ── Request / Response Models ────────────────────────────────────────────────


class SettingsUpdateRequest(BaseModel):
    country_code: Optional[str] = Field(None, max_length=3)
    city: Optional[str] = Field(None, max_length=255)
    currency_code: Optional[str] = Field(None, max_length=3)
    measurement_system: Optional[str] = Field(None, pattern=r"^(metric|imperial)$")
    dietary_preferences: Optional[dict[str, bool]] = None
    monthly_budget: Optional[Decimal] = Field(None, ge=0)
    timezone: Optional[str] = Field(None, max_length=50)
    shopping_culture: Optional[str] = Field(None, pattern=r"^(bazaar|supermarket|mixed)$")


class PurchaseTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class AddItemRequest(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(default="🥫 Бакалея и специи", max_length=100)
    quantity: Decimal = Field(default=Decimal("1.0"), gt=0)
    unit: str = Field(default="кг", max_length=20)
    price_paid: Decimal = Field(default=Decimal("0"), ge=0)
    store_name: Optional[str] = Field(None, max_length=255)


class TogglePurchasedRequest(BaseModel):
    is_purchased: bool


class ChecklistItemResponse(BaseModel):
    id: str
    item_name: str
    category: str = "🥫 Бакалея и специи"
    quantity: str
    unit: str
    price_paid: str
    currency_code: str
    store_name: Optional[str]
    is_purchased: bool
    created_at: str


class UserProfileResponse(BaseModel):
    user_id: str
    first_name: Optional[str]
    settings: dict[str, Any]
    total_items: int
    total_spent: str


# ── Middleware ────────────────────────────────────────────────────────────────


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# ── Health ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "OmniCart AI", "version": "1.0.0"}


# ── User Profile ─────────────────────────────────────────────────────────────


@app.get("/api/v1/profile", tags=["User"], response_model=UserProfileResponse)
async def get_profile(tg_user: AuthUser, db: DBSession) -> UserProfileResponse:
    user = await get_or_create_user(tg_user, db)

    purchases_result = await db.execute(
        select(PurchaseHistory).where(PurchaseHistory.user_id == user.id)
    )
    purchases = list(purchases_result.scalars().all())
    total_spent = sum((p.price_paid for p in purchases), Decimal("0"))

    user_settings = user.settings
    settings_dict: dict[str, Any] = {}
    if user_settings:
        settings_dict = {
            "country_code": user_settings.country_code,
            "city": user_settings.city,
            "currency_code": user_settings.currency_code,
            "measurement_system": user_settings.measurement_system,
            "dietary_preferences": user_settings.dietary_preferences or {},
            "monthly_budget": str(user_settings.monthly_budget) if user_settings.monthly_budget else None,
            "timezone": user_settings.timezone,
            "shopping_culture": user_settings.shopping_culture,
        }

    return UserProfileResponse(
        user_id=str(user.id),
        first_name=user.first_name,
        settings=settings_dict,
        total_items=len(purchases),
        total_spent=str(total_spent),
    )


@app.put("/api/v1/settings", tags=["User"])
async def update_settings(
    body: SettingsUpdateRequest,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, str]:
    user = await get_or_create_user(tg_user, db)

    if user.settings is None:
        user_settings = UserSettings(user_id=user.id)
        db.add(user_settings)
        await db.flush()
    else:
        user_settings = user.settings

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if isinstance(value, str):
            value = _sanitize_string(value)
        setattr(user_settings, field_name, value)

    await db.commit()
    return {"status": "updated"}


# ── Checklist (Shopping List) ────────────────────────────────────────────────


@app.get(
    "/api/v1/checklist",
    tags=["Checklist"],
    response_model=list[ChecklistItemResponse],
)
async def get_checklist(
    tg_user: AuthUser,
    db: DBSession,
    include_purchased: bool = Query(False),
) -> list[ChecklistItemResponse]:
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    query = select(PurchaseHistory).where(PurchaseHistory.user_id == cart_id)
    if not include_purchased:
        query = query.where(PurchaseHistory.is_purchased == False)  # noqa: E712
    query = query.order_by(PurchaseHistory.is_purchased.asc(), PurchaseHistory.category.asc(), PurchaseHistory.created_at.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    return [
        ChecklistItemResponse(
            id=str(item.id),
            item_name=item.item_name,
            category=item.category or "🥫 Бакалея и специи",
            quantity=str(item.quantity),
            unit=item.unit,
            price_paid=str(item.price_paid),
            currency_code=item.currency_code or "UZS",
            store_name=item.store_name,
            is_purchased=item.is_purchased,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]


@app.post("/api/v1/checklist", tags=["Checklist"], status_code=201)
async def add_checklist_item(
    body: AddItemRequest,
    tg_user: AuthUser,
    db: DBSession,
) -> ChecklistItemResponse:
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id
    cat = body.category or UniversalAIParser._categorize_fallback(body.item_name)

    item = PurchaseHistory(
        user_id=cart_id,
        item_name=_sanitize_string(body.item_name),
        category=cat,
        quantity=body.quantity,
        unit=body.unit,
        price_paid=body.price_paid,
        currency_code="UZS",
        store_name=_sanitize_string(body.store_name) if body.store_name else None,
        country_code="UZ",
        city="Гулистан",
        is_purchased=False,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return ChecklistItemResponse(
        id=str(item.id),
        item_name=item.item_name,
        category=item.category,
        quantity=str(item.quantity),
        unit=item.unit,
        price_paid=str(item.price_paid),
        currency_code=item.currency_code,
        store_name=item.store_name,
        is_purchased=item.is_purchased,
        created_at=item.created_at.isoformat(),
    )


@app.patch("/api/v1/checklist/{item_id}/toggle", tags=["Checklist"])
async def toggle_purchased(
    item_id: str,
    body: TogglePurchasedRequest,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    user = await get_or_create_user(tg_user, db)

    try:
        uid = uuid.UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid item ID") from exc

    result = await db.execute(
        select(PurchaseHistory).where(
            PurchaseHistory.id == uid,
            PurchaseHistory.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_purchased = body.is_purchased
    if body.is_purchased:
        item.purchased_at = datetime.now(timezone.utc)
    await db.commit()

    return {"id": str(item.id), "is_purchased": item.is_purchased}


@app.delete("/api/v1/checklist/{item_id}", tags=["Checklist"], status_code=204)
async def delete_checklist_item(
    item_id: str,
    tg_user: AuthUser,
    db: DBSession,
) -> None:
    user = await get_or_create_user(tg_user, db)

    try:
        uid = uuid.UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid item ID") from exc

    result = await db.execute(
        select(PurchaseHistory).where(
            PurchaseHistory.id == uid,
            PurchaseHistory.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()


# ── AI: Parse Purchase Text ──────────────────────────────────────────────────


@app.post("/api/v1/ai/parse-purchase", tags=["AI"])
async def ai_parse_purchase(
    body: PurchaseTextRequest,
    tg_user: AuthUser,
    db: DBSession,
    bai: Annotated[BAIClient, Depends(get_bai)],
) -> dict[str, Any]:
    user = await get_or_create_user(tg_user, db)
    user_settings = user.settings

    country = user_settings.country_code if user_settings else "US"
    city = user_settings.city if user_settings else "New York"
    currency = user_settings.currency_code if user_settings else "USD"
    measurement = user_settings.measurement_system if user_settings else "metric"
    culture = user_settings.shopping_culture if user_settings else "supermarket"
    dietary = user_settings.dietary_preferences if user_settings else None
    budget = user_settings.monthly_budget if user_settings else None

    sanitized_text = _sanitize_string(body.text)

    try:
        parsed = await bai.parse_purchase_text(
            sanitized_text,
            country=country,
            city=city,
            currency=currency,
            measurement=measurement,
            shopping_culture=culture,
            dietary=dietary,
            budget=budget,
        )
    except BAIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    created_items: list[dict[str, Any]] = []
    for pi in parsed.items:
        purchase = PurchaseHistory(
            user_id=user.id,
            raw_input_text=sanitized_text,
            item_name=_sanitize_string(pi.item_name),
            quantity=pi.quantity,
            unit=pi.unit,
            price_paid=pi.price,
            currency_code=pi.currency,
            store_name=_sanitize_string(pi.store_name) if pi.store_name else None,
            country_code=country,
            city=city,
            is_purchased=False,
            ai_parsed_data=pi.model_dump(mode="json"),
        )
        db.add(purchase)
        created_items.append({
            "item_name": pi.item_name,
            "quantity": str(pi.quantity),
            "unit": pi.unit,
            "price": str(pi.price),
            "currency": pi.currency,
            "store_name": pi.store_name,
            "confidence": str(pi.confidence),
        })

    await db.commit()

    return {
        "parsed_items": created_items,
        "interpretation": parsed.raw_interpretation,
        "count": len(created_items),
    }


# ── AI: Price Analysis ──────────────────────────────────────────────────────


@app.get("/api/v1/ai/price-analysis", tags=["AI"])
async def ai_price_analysis(
    tg_user: AuthUser,
    db: DBSession,
    bai: Annotated[BAIClient, Depends(get_bai)],
) -> dict[str, Any]:
    user = await get_or_create_user(tg_user, db)
    user_settings = user.settings
    country = user_settings.country_code if user_settings else "US"
    city = user_settings.city if user_settings else "New York"
    currency = user_settings.currency_code if user_settings else "USD"

    purchases_result = await db.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.user_id == user.id)
        .order_by(PurchaseHistory.created_at.desc())
        .limit(50)
    )
    purchases = purchases_result.scalars().all()

    if not purchases:
        return {"analyses": [], "market_summary": "No purchase history to analyze."}

    user_purchase_data = [
        {
            "item_name": p.item_name,
            "price": str(p.price_paid),
            "quantity": str(p.quantity),
            "unit": p.unit,
            "store": p.store_name,
            "date": p.purchased_at.isoformat() if p.purchased_at else "",
        }
        for p in purchases
    ]

    price_result = await db.execute(
        select(LocalPriceIndex)
        .where(
            LocalPriceIndex.country_code == country,
            LocalPriceIndex.city == city,
        )
        .limit(200)
    )
    price_indices = price_result.scalars().all()

    local_data = [
        {
            "item_id": str(lp.product_id),
            "price": str(lp.price),
            "unit": lp.unit,
            "store": lp.store_name,
            "confidence": str(lp.confidence_score),
        }
        for lp in price_indices
    ]

    try:
        analysis = await bai.analyze_prices(
            user_purchase_data,
            local_data,
            country=country,
            city=city,
            currency=currency,
        )
    except BAIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "analyses": [a.model_dump(mode="json") for a in analysis.analyses],
        "market_summary": analysis.market_summary,
    }


# ── Health, Webhook & Cron (Serverless Support) ──────────────────────────────


@app.get("/api/health")
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint indicating server and service statuses."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "OmniCart AI",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "serverless": settings.is_serverless,
        "database_configured": bool(settings.database_url),
        "redis_configured": bool(settings.redis_url),
    }


@app.get("/api/webhook")
@app.get("/webhook")
async def telegram_webhook_info() -> dict[str, str]:
    return {"status": "ok", "message": "OmniCart AI Telegram Webhook is active and waiting for POST updates"}


async def _process_telegram_update(body: dict[str, Any]) -> None:
    """Background processor for Telegram updates to prevent webhook timeouts."""
    settings = get_settings()
    dp = get_dispatcher()
    async with Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    ) as bot:
        try:
            session_factory = _session_factory
            if session_factory is None:
                await _init_resources()
                session_factory = _session_factory

            if session_factory:
                async with session_factory() as db:
                    update = Update.model_validate(body, context={"bot": bot})
                    await dp.feed_update(bot=bot, update=update, db_session=db)
            else:
                logger.error("No DB session factory available for update processing")
        except Exception as exc:
            logger.exception("Error processing Telegram update in background: %s", exc)


@app.post("/api/webhook")
@app.post("/api/webhook.py")
@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    secret_token: Annotated[Optional[str], Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, Any]:
    """
    Lightning-fast Telegram Bot Webhook endpoint.
    Instantly responds {"ok": True} (<50ms) to prevent timeouts and duplicate retry loops.
    Heavy processing is handed off to background tasks.
    """
    settings = get_settings()
    if settings.telegram_webhook_secret and secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret token")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}")

    background_tasks.add_task(_process_telegram_update, body)
    return {"ok": True}


@app.get("/api/v1/bot/setup-webhook")
@app.post("/api/v1/bot/setup-webhook")
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


# ── Xiaomi Notes & Guliston Market Endpoints ─────────────────────────────────

class XiaomiNotesImportBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


@app.post("/api/v1/notes/import-xiaomi", tags=["Xiaomi Notes"])
async def import_xiaomi_notes(
    body: XiaomiNotesImportBody,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Parse notes copied from Xiaomi Notes or any app and import into user checklist."""
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    parsed_result = await UniversalAIParser.parse_any_text(body.text)

    added = []
    for it in parsed_result.items:
        item = PurchaseHistory(
            user_id=cart_id,
            item_name=it.name,
            category=it.category,
            quantity=Decimal(str(it.qty)),
            unit=it.unit,
            price_paid=Decimal(str(it.estimated_price)),
            currency_code="UZS",
            country_code="UZ",
            city="Гулистан",
            is_purchased=False,
            raw_input_text="AI Import WebApp",
        )
        db.add(item)
        added.append(it.model_dump())

    await db.commit()
    return {"status": "success", "count": len(added), "items": added}


class GulistonAdvisorBody(BaseModel):
    items: Optional[list[str]] = None


@app.post("/api/v1/market/guliston-advisor", tags=["Guliston Market"])
async def get_guliston_advice_api(
    body: GulistonAdvisorBody,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Analyzes market items between Guliston Dehqon Bozori and Korzinka Guliston."""
    from services.guliston_market_service import GulistonMarketService

    user = await get_or_create_user(tg_user, db)
    items_to_check = body.items
    if not items_to_check:
        res = await db.execute(
            select(PurchaseHistory.item_name)
            .where(PurchaseHistory.user_id == user.id, PurchaseHistory.is_purchased == False)
            .limit(20)
        )
        items_to_check = list(res.scalars().all())

    if not items_to_check:
        items_to_check = ["говядина", "картофель", "лук", "растительное масло", "молоко", "яйца", "рис лазер"]

    return GulistonMarketService.analyze_shopping_list(items_to_check)


@app.get("/api/v1/market/plov-calculator", tags=["Guliston Market"])
async def get_plov_calculator_api(
    servings: int = Query(6, ge=1, le=100),
) -> dict[str, Any]:
    """Calculates plov ingredients and estimated cost in Guliston."""
    from services.guliston_market_service import GulistonMarketService

    return GulistonMarketService.get_plov_calculator(servings)


@app.get("/api/cron")
@app.post("/api/cron")
async def cron_trigger(
    request: Request,
) -> dict[str, Any]:
    """Vercel Cron endpoint to run scheduled replenishment calculations and price aggregations."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization", "")

    if settings.cron_secret:
        expected = f"Bearer {settings.cron_secret}"
        if auth_header != expected:
            raise HTTPException(status_code=401, detail="Unauthorized cron trigger")

    if _session_factory is None:
        await _init_resources()

    from services.worker import compute_replenishment_intervals, update_price_index_from_purchases

    ctx = {"session_factory": _session_factory}
    intervals_updated = await compute_replenishment_intervals(ctx)
    prices_updated = await update_price_index_from_purchases(ctx)

    # Also sync daily Redis market prices
    redis = await get_redis()
    await PriceCronService.sync_daily_prices(redis)

    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "replenishment_intervals_updated": intervals_updated,
        "price_indexes_processed": prices_updated,
    }


# ── Fast Market Autocomplete & Crowdsourcing ─────────────────────────────────

@app.get("/api/v1/market/autocomplete", tags=["Guliston Market"])
async def market_autocomplete(
    q: str = Query(..., min_length=1, max_length=100),
) -> dict[str, Any]:
    """Sub-15ms fast autocomplete from Upstash Redis cache."""
    redis = await get_redis()
    matches = await PriceCronService.autocomplete(q, redis, limit=6)
    return {"query": q, "results": matches}


class ReportPriceBody(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)


@app.post("/api/v1/market/report-price", tags=["Guliston Market"])
async def report_market_price(
    body: ReportPriceBody,
) -> dict[str, Any]:
    """Crowdsourcing: user reports actual price at Guliston bazaar."""
    redis = await get_redis()
    await PriceCronService.update_user_price(body.item_name, body.price, redis)
    return {"status": "success", "item": body.item_name, "price": body.price}


@app.get("/api/cron/sync-prices")
@app.post("/api/cron/sync-prices")
async def cron_sync_prices(
    request: Request,
) -> dict[str, Any]:
    """Syncs bazaar & supermarket prices to Upstash Redis."""
    redis = await get_redis()
    result = await PriceCronService.sync_daily_prices(redis)
    return result


# ── Family Cart & AI Core Endpoints ──────────────────────────────────────────

class JoinFamilyBody(BaseModel):
    family_cart_id: str


@app.post("/api/v1/cart/join-family", tags=["Family Cart"])
async def join_family_cart(
    body: JoinFamilyBody,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Joins another user's family cart for shared real-time shopping."""
    user = await get_or_create_user(tg_user, db)
    try:
        target_uuid = uuid.UUID(body.family_cart_id)
        user.family_cart_id = target_uuid
        await db.commit()
        return {"status": "joined", "family_cart_id": str(target_uuid)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid family cart UUID: {exc}")


class UniversalParseBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


@app.post("/api/v1/ai/parse-text", tags=["AI Core"])
async def parse_text_endpoint(
    body: UniversalParseBody,
) -> dict[str, Any]:
    """Universal AI parser for any free text or copied notes."""
    result = await UniversalAIParser.parse_any_text(body.text)
    return result.model_dump()


class RecipeParseBody(BaseModel):
    recipe: str = Field(..., min_length=1, max_length=20000)
    servings: int = Field(default=4, ge=1, le=50)


@app.post("/api/v1/ai/parse-recipe", tags=["AI Core"])
async def parse_recipe_endpoint(
    body: RecipeParseBody,
) -> dict[str, Any]:
    """Reverse recipe analysis: scales ingredients for N servings."""
    result = await UniversalAIParser.parse_recipe(body.recipe, servings=body.servings)
    return result.model_dump()


# ── Error Handlers ───────────────────────────────────────────────────────────


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
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )
