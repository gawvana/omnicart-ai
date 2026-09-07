"""
OmniCart AI — SQLAlchemy 2.0 async ORM models.

Per-user tenant isolation: every row carries `user_internal_id` (SHA-256 hashed Telegram ID).
All datetime columns are timezone-aware UTC.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.config import get_settings


# ── Engine & Session Factory ─────────────────────────────────────────────────

def build_engine() -> tuple[object, async_sessionmaker[object]]:
    settings = get_settings()
    engine_kwargs: dict[str, Any] = {
        "echo": settings.debug,
    }
    if "sqlite" not in settings.database_url:
        engine_kwargs.update({
            "pool_size": 20,
            "max_overflow": 10,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        })
    engine = create_async_engine(settings.database_url, **engine_kwargs)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


# ── Base ─────────────────────────────────────────────────────────────────────

class Base(AsyncAttrs, DeclarativeBase):
    """Abstract declarative base with async attrs support."""

    type_annotation_map = {
        uuid.UUID: Uuid(as_uuid=True),
        dict: JSON,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_telegram_id(telegram_id: int) -> str:
    """One-way SHA-256 hash of Telegram user ID for per-user tenancy."""
    return hashlib.sha256(str(telegram_id).encode("utf-8")).hexdigest()


# ── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    """
    Core user record.
    `telegram_id_hash` = SHA-256(telegram_id) — stored instead of raw ID for privacy.
    `telegram_id_encrypted` may store an encrypted form if recovery is needed.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    telegram_id_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    telegram_id_encrypted: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="ru")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    family_cart_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    # Relationships
    settings: Mapped[Optional["UserSettings"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    purchases: Mapped[list["PurchaseHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    predictive_intervals: Mapped[list["PredictiveInterval"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class UserSettings(Base):
    """Per-user preferences: locale, currency, measurement system, dietary filters."""

    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    country_code: Mapped[str] = mapped_column(String(3), default="UZ")
    city: Mapped[str] = mapped_column(String(255), default="Гулистан")
    currency_code: Mapped[str] = mapped_column(String(3), default="UZS")
    measurement_system: Mapped[str] = mapped_column(
        String(10), default="metric"
    )  # 'metric' | 'imperial'
    dietary_preferences: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict
    )  # e.g. {"halal": true}
    monthly_budget: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tashkent")
    shopping_culture: Mapped[str] = mapped_column(
        String(20), default="mixed"
    )  # 'bazaar' | 'supermarket' | 'mixed'

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="settings")


class Product(Base):
    """
    Canonical product catalogue.
    Normalized names, categories, and default units of measurement.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    default_unit: Mapped[str] = mapped_column(String(20), default="kg")  # kg, lb, pcs, l
    aliases: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict
    )  # {"ru": ["картошка", "картофель"], "en": ["potato"]}
    nutrition_per_100g: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # {"calories": 77, "protein": 2, ...}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # Relationships
    price_indices: Mapped[list["LocalPriceIndex"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseHistory(Base):
    """
    Individual purchase record tied to a user.
    Stores quantity, price paid, store, and AI-parsed metadata.
    """

    __tablename__ = "purchase_history"
    __table_args__ = (
        Index("ix_purchase_user_date", "user_id", "purchased_at"),
        Index("ix_purchase_item_created", "item_name", "created_at"),
        Index("ix_purchase_product_created", "product_id", "created_at"),
        CheckConstraint("quantity > 0", name="ck_positive_quantity"),
        CheckConstraint("price_paid >= 0", name="ck_nonneg_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_input_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="Бакалея и специи")
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("1.0"), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="кг")
    price_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="UZS")
    store_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str] = mapped_column(String(3), default="UZ")
    city: Mapped[str] = mapped_column(String(255), default="Гулистан")
    is_purchased: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_parsed_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    purchased_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="purchases")


class PredictiveInterval(Base):
    """
    AI-computed consumption velocity per product per user.
    Used for predictive replenishment notifications.
    """

    __tablename__ = "predictive_intervals"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_interval"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    avg_consumption_per_day: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )
    avg_purchase_interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    last_purchase_quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    estimated_depletion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("0.5")
    )  # 0.000 – 1.000
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="predictive_intervals")


class LocalPriceIndex(Base):
    """
    Crowdsourced / AI-enriched local price data.
    Enables price comparison and market analytics across geographies.
    """

    __tablename__ = "local_price_index"
    __table_args__ = (
        Index("ix_price_geo_item", "country_code", "city", "product_id"),
        CheckConstraint("price > 0", name="ck_positive_price"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    store_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="USD")
    unit: Mapped[str] = mapped_column(String(20), default="kg")
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("0.5")
    )
    source: Mapped[str] = mapped_column(
        String(50), default="user_report"
    )  # 'user_report' | 'ai_parsed' | 'api_feed'
    reported_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="price_indices")


class PriceHistory(Base):
    """
    Crowdsourced and monitored price logs for Guliston and local markets.
    Used by Market Price Estimator for IQR outlier filtering, median calculations, and price trends.
    """

    __tablename__ = "price_history"
    __table_args__ = (
        Index("ix_price_history_item_created", "item_name", "created_at"),
        Index("ix_price_history_market_created", "market_name", "created_at"),
        CheckConstraint("price > 0", name="ck_price_history_positive_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    market_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reporter_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )

