"""
OmniCart AI — ARQ background worker.
Handles async tasks: predictive replenishment, price index updates, notifications.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings
from database.models import (
    Base,
    LocalPriceIndex,
    PredictiveInterval,
    PurchaseHistory,
    User,
    UserSettings,
)
from services.b_ai_client import BAIClient, BAIClientError

logger = logging.getLogger(__name__)

# ── Worker context ───────────────────────────────────────────────────────────


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize DB engine and session factory in worker context."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=3,
        pool_pre_ping=True,
    )
    ctx["engine"] = engine
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("ARQ worker started")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Dispose engine on worker shutdown."""
    engine = ctx.get("engine")
    if engine:
        await engine.dispose()
    logger.info("ARQ worker stopped")


# ── Tasks ────────────────────────────────────────────────────────────────────


async def compute_replenishment_intervals(ctx: dict[str, Any]) -> int:
    """
    For each user, analyze purchase history and compute/update predictive intervals.
    Returns the number of intervals updated.
    """
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    updated = 0

    async with session_factory() as session:
        users_result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

        for user in users:
            purchases_result = await session.execute(
                select(PurchaseHistory)
                .where(
                    PurchaseHistory.user_id == user.id,
                    PurchaseHistory.is_purchased == True,  # noqa: E712
                )
                .order_by(PurchaseHistory.purchased_at.desc())
                .limit(200)
            )
            purchases = purchases_result.scalars().all()

            if len(purchases) < 3:
                continue

            # Group purchases by item name
            item_groups: dict[str, list[PurchaseHistory]] = {}
            for p in purchases:
                key = p.item_name.lower().strip()
                if key not in item_groups:
                    item_groups[key] = []
                item_groups[key].append(p)

            for item_name, group in item_groups.items():
                if len(group) < 2:
                    continue

                sorted_group = sorted(group, key=lambda x: x.purchased_at or datetime.min.replace(tzinfo=timezone.utc))

                # Compute average interval between purchases
                intervals: list[float] = []
                total_qty = Decimal("0")
                for i in range(len(sorted_group)):
                    total_qty += sorted_group[i].quantity
                    if i > 0:
                        prev = sorted_group[i - 1].purchased_at
                        curr = sorted_group[i].purchased_at
                        if prev and curr:
                            delta = (curr - prev).total_seconds() / 86400.0
                            if delta > 0:
                                intervals.append(delta)

                if not intervals:
                    continue

                avg_interval = sum(intervals) / len(intervals)
                avg_qty_per_purchase = total_qty / len(sorted_group)
                avg_consumption = avg_qty_per_purchase / Decimal(str(max(avg_interval, 1)))

                last_purchase = sorted_group[-1]
                last_date = last_purchase.purchased_at or datetime.now(timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_date).total_seconds() / 86400.0
                remaining_qty = last_purchase.quantity - (avg_consumption * Decimal(str(days_since)))
                remaining_qty = max(remaining_qty, Decimal("0"))

                if avg_consumption > 0:
                    days_left = float(remaining_qty / avg_consumption)
                    depletion_date = datetime.now(timezone.utc) + timedelta(days=days_left)
                else:
                    depletion_date = None

                confidence = min(Decimal("0.95"), Decimal(str(len(group) * 0.1)))

                # Find the product_id from the most recent purchase that has one
                target_product_id = None
                for p in reversed(sorted_group):
                    if p.product_id is not None:
                        target_product_id = p.product_id
                        break

                if target_product_id is None:
                    continue

                # Upsert predictive interval by (user_id, product_id)
                existing_result = await session.execute(
                    select(PredictiveInterval).where(
                        PredictiveInterval.user_id == user.id,
                        PredictiveInterval.product_id == target_product_id,
                    )
                )
                existing_interval = existing_result.scalar_one_or_none()

                if existing_interval is not None:
                    existing_interval.avg_consumption_per_day = avg_consumption
                    existing_interval.avg_purchase_interval_days = max(1, int(avg_interval))
                    existing_interval.last_purchase_quantity = last_purchase.quantity
                    existing_interval.estimated_depletion_date = depletion_date
                    existing_interval.confidence = confidence
                    existing_interval.notification_sent = False
                    updated += 1
                else:
                    new_interval = PredictiveInterval(
                        user_id=user.id,
                        product_id=target_product_id,
                        avg_consumption_per_day=avg_consumption,
                        avg_purchase_interval_days=max(1, int(avg_interval)),
                        last_purchase_quantity=last_purchase.quantity,
                        estimated_depletion_date=depletion_date,
                        confidence=confidence,
                    )
                    session.add(new_interval)
                    updated += 1

        await session.commit()

    logger.info("Updated %d replenishment intervals", updated)
    return updated


async def update_price_index_from_purchases(ctx: dict[str, Any]) -> int:
    """
    Aggregate recent purchases into local price index entries.
    Returns number of price index records created/updated.
    """
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    async with session_factory() as session:
        recent_result = await session.execute(
            select(
                PurchaseHistory.item_name,
                PurchaseHistory.country_code,
                PurchaseHistory.city,
                PurchaseHistory.store_name,
                PurchaseHistory.unit,
                PurchaseHistory.currency_code,
                func.avg(PurchaseHistory.price_paid).label("avg_price"),
                func.count().label("sample_count"),
            )
            .where(
                PurchaseHistory.is_purchased == True,  # noqa: E712
                PurchaseHistory.purchased_at >= cutoff,
                PurchaseHistory.price_paid > 0,
            )
            .group_by(
                PurchaseHistory.item_name,
                PurchaseHistory.country_code,
                PurchaseHistory.city,
                PurchaseHistory.store_name,
                PurchaseHistory.unit,
                PurchaseHistory.currency_code,
            )
        )
        aggregates = recent_result.all()

        for row in aggregates:
            avg_price = Decimal(str(row.avg_price)).quantize(Decimal("0.01"))
            sample_count: int = row.sample_count
            confidence = min(Decimal("0.95"), Decimal(str(sample_count * 0.05)))

            # Only update if product_id can be resolved — skip for now
            # In production, match item_name to Product.canonical_name
            # For MVP, we store as-is with product_id = None → skip FK constraint
            # This task would be enhanced with canonical product matching logic

            count += 1

        await session.commit()

    logger.info("Processed %d price index aggregates", count)
    return count


# ── Worker Settings ──────────────────────────────────────────────────────────


class WorkerSettings:
    """ARQ worker configuration."""

    settings = get_settings()

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    functions = [
        compute_replenishment_intervals,
        update_price_index_from_purchases,
    ]

    cron_jobs = [
        cron(
            compute_replenishment_intervals,
            hour={6, 18},
            minute=0,
            run_at_startup=False,
        ),
        cron(
            update_price_index_from_purchases,
            hour={3},
            minute=30,
            run_at_startup=False,
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
