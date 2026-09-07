"""
OmniCart AI — Guliston (Syrdarya) Local Market Analytics Service.
Provides:
- Statistical Market Price Estimator with IQR anomaly filtering & median computation
- Crowdsourced and recorded price history persistence
- Redis caching with 1-hour TTL
- Basket split recommendation: Guliston Dehqon Bozori vs. Korzinka Guliston
- Authentic Guliston Plov (Osh) ingredient cost calculator
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Static Market Knowledge Base (Fallback & Fast Reference) ─────────────────

GULISTON_MARKET_INDEX: dict[str, dict[str, Any]] = {
    "говядина": {
        "bazaar_name": "Деҳқон Бозори (Мясной павильон)",
        "bazaar_price": 90000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 105000,
        "unit": "кг",
        "recommendation": "Мясо выгоднее и свежее брать утром на Деҳқон Бозори до 11:00.",
        "best_place": "bazaar",
    },
    "баранина": {
        "bazaar_name": "Деҳқон Бозори (Мясной павильон)",
        "bazaar_price": 95000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 115000,
        "unit": "кг",
        "recommendation": "Свежая баранина лучшего качества на центральном Деҳқон Бозори.",
        "best_place": "bazaar",
    },
    "куриное филе": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 46000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 48500,
        "unit": "кг",
        "recommendation": "В Корзинке часто бывают охлажденные лотки по акции, разница минимальна.",
        "best_place": "supermarket",
    },
    "картофель": {
        "bazaar_name": "Деҳқон Бозори (Овощные ряды)",
        "bazaar_price": 4500,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 6200,
        "unit": "кг",
        "recommendation": "Сетками и мешками выгоднее брать на въезде в Деҳқон Бозори.",
        "best_place": "bazaar",
    },
    "лук репчатый": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 2500,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 4000,
        "unit": "кг",
        "recommendation": "На базаре лук значительно дешевле, особенно при покупке от 5 кг.",
        "best_place": "bazaar",
    },
    "морковь": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 3000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 4500,
        "unit": "кг",
        "recommendation": "Для плова (желтую и красную) лучше отбирать вручную на Деҳқон Бозори.",
        "best_place": "bazaar",
    },
    "помидоры": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 12000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 18000,
        "unit": "кг",
        "recommendation": "Юсуповские и розовые помидоры — только на базаре у частников.",
        "best_place": "bazaar",
    },
    "огурцы": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 8000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 13500,
        "unit": "кг",
        "recommendation": "Свежий утренний сбор на базаре вдвое дешевле супермаркета.",
        "best_place": "bazaar",
    },
    "растительное масло": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 20000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 18500,
        "unit": "л",
        "recommendation": "Бутилированное подсолнечное масло (Олейна, Щедрое Лето) дешевле в Корзинке по акциям.",
        "best_place": "supermarket",
    },
    "хлопковое масло": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 17000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 19500,
        "unit": "л",
        "recommendation": "Настоящее очищенное пахта-масло для плова надежнее брать на базаре.",
        "best_place": "bazaar",
    },
    "рис лазер": {
        "bazaar_name": "Деҳқон Бозори (Рисовый ряд)",
        "bazaar_price": 26000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 32000,
        "unit": "кг",
        "recommendation": "Отборный хорезмский рис Лазер лучше пробовать и брать в рисовом ряду базара.",
        "best_place": "bazaar",
    },
    "рис аланга": {
        "bazaar_name": "Деҳқон Бозори (Рисовый ряд)",
        "bazaar_price": 18000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 23000,
        "unit": "кг",
        "recommendation": "Аланга на каждый день доступнее на центральном рынке.",
        "best_place": "bazaar",
    },
    "молоко": {
        "bazaar_name": "Деҳқон Бозори (домашнее)",
        "bazaar_price": 9000,
        "supermarket_name": "Корзинка Гулистан (пастеризованное)",
        "supermarket_price": 13500,
        "unit": "л",
        "recommendation": "Пастеризованное ультрапак (Musaffo, Nestlé) удобнее в Корзинке, домашнее парное — на базаре.",
        "best_place": "supermarket",
    },
    "яйца": {
        "bazaar_name": "Деҳқон Бозори (лоток 30 шт)",
        "bazaar_price": 38000,
        "supermarket_name": "Корзинка Гулистан (лоток 30 шт)",
        "supermarket_price": 44000,
        "unit": "лоток",
        "recommendation": "Целыми лотками по 30 шт значительно выгоднее на оптовых точках базара.",
        "best_place": "bazaar",
    },
    "сахар": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 13500,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 14200,
        "unit": "кг",
        "recommendation": "Разница минимальна, фасованный чистый сахар удобнее брать в супермаркете.",
        "best_place": "supermarket",
    },
    "мука 1 сорт": {
        "bazaar_name": "Деҳқон Бозори (мешок/развес)",
        "bazaar_price": 7500,
        "supermarket_name": "Корзинка Гулистан (фасовка)",
        "supermarket_price": 9200,
        "unit": "кг",
        "recommendation": "Казахстанская мука высшего и 1 сорта дешевле на мучных складах базара.",
        "best_place": "bazaar",
    },
    "лепешка": {
        "bazaar_name": "Янги Бозор / Тандыр",
        "bazaar_price": 4000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 5500,
        "unit": "шт",
        "recommendation": "Горячие лепешки прямо из тандыра вкуснее и дешевле в махаллинских тандырных.",
        "best_place": "bazaar",
    },
    "чай черный": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 28000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 26000,
        "unit": "пачка",
        "recommendation": "Брендовый чай (Greenfield, Tess, Beta) в Корзинке с гарантией подлинности и скидками.",
        "best_place": "supermarket",
    },
    "бытовая химия / порошок": {
        "bazaar_name": "Деҳқон Бозори",
        "bazaar_price": 65000,
        "supermarket_name": "Корзинка Гулистан",
        "supermarket_price": 59000,
        "unit": "упаковка 3кг",
        "recommendation": "Стиральные порошки и химию (Ariel, Persil, Fairy) надежнее и дешевле брать в Корзинке.",
        "best_place": "supermarket",
    },
}


# ── DTOs ─────────────────────────────────────────────────────────────────────

class PricePointDTO(BaseModel):
    price: Decimal = Field(..., decimal_places=2, ge=Decimal("0.00"))
    market_name: str = Field(..., min_length=1, max_length=128)
    recorded_at: datetime


class MarketPriceEstimate(BaseModel):
    item_name: str
    sample_size: int
    min_price: Decimal
    max_price: Decimal
    average_price: Decimal
    median_price: Decimal
    recommended_retail_price: Decimal
    currency: str = "UZS"
    price_spread_percentage: Decimal
    last_updated: datetime


# ── Service ──────────────────────────────────────────────────────────────────

class GulistonMarketService:
    """
    Market intelligence, price comparison, statistical anomaly filtering (IQR),
    and shopping optimization for the city of Guliston.
    """

    def __init__(self, session: AsyncSession, redis: Any = None):
        self._session = session
        self._redis = redis

    async def calculate_market_estimate(
        self,
        item_name: str,
        lookback_days: int = 14,
    ) -> Optional[MarketPriceEstimate]:
        """
        Calculates robust market price estimate using historical records.
        Applies IQR (Interquartile Range) to eliminate outlier data points.
        Caches results in Redis with 1-hour TTL.
        """
        if not item_name or not item_name.strip():
            raise ValueError("Имя товара не может быть пустым.")

        normalized_item_name = item_name.strip().lower()
        cache_key = f"market:estimate:{normalized_item_name}:{lookback_days}"

        # 1. Try Redis cache
        if self._redis is not None:
            try:
                cached_data = await self._redis.get(cache_key)
                if cached_data:
                    return MarketPriceEstimate.model_validate_json(cached_data)
            except Exception as exc:
                logger.debug("Redis cache get error for %s: %s", cache_key, exc)

        # 2. Query database for PriceHistory
        threshold_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        from database.models import PriceHistory

        query = (
            select(PriceHistory.price, PriceHistory.market_name, PriceHistory.created_at)
            .where(
                func.lower(PriceHistory.item_name) == normalized_item_name,
                PriceHistory.created_at >= threshold_date,
            )
            .order_by(PriceHistory.price.asc())
        )

        result = await self._session.execute(query)
        rows: Sequence[Any] = result.all()

        # Fallback to static catalog if no DB price history records exist yet
        if not rows:
            logger.info("Записи цен для товара '%s' не найдены в БД. Проверка базового каталога.", normalized_item_name)
            static_info = self.find_product_info(item_name)
            if static_info:
                b_price = Decimal(str(static_info["bazaar_price"]))
                s_price = Decimal(str(static_info["supermarket_price"]))
                min_p = min(b_price, s_price)
                max_p = max(b_price, s_price)
                avg_p = ((b_price + s_price) / Decimal("2")).quantize(Decimal("0.01"))
                spread = (((max_p - min_p) / min_p) * Decimal("100")).quantize(Decimal("0.01")) if min_p > 0 else Decimal("0.00")
                rrp = (b_price * Decimal("1.05")).quantize(Decimal("0.01"))

                estimate = MarketPriceEstimate(
                    item_name=item_name.strip(),
                    sample_size=2,
                    min_price=min_p.quantize(Decimal("0.01")),
                    max_price=max_p.quantize(Decimal("0.01")),
                    average_price=avg_p,
                    median_price=min_p.quantize(Decimal("0.01")),
                    recommended_retail_price=rrp,
                    currency="UZS",
                    price_spread_percentage=spread,
                    last_updated=datetime.now(timezone.utc),
                )
                return estimate
            return None

        prices: List[Decimal] = [Decimal(str(row[0])) for row in rows]
        clean_prices = self._remove_outliers_iqr(prices)

        if not clean_prices:
            clean_prices = prices

        sample_size = len(clean_prices)
        min_p = clean_prices[0]
        max_p = clean_prices[-1]
        avg_p = sum(clean_prices) / Decimal(sample_size)
        median_p = self._calculate_median(clean_prices)
        rrp = (median_p * Decimal("1.05")).quantize(Decimal("0.01"))

        if min_p > Decimal("0"):
            spread = (((max_p - min_p) / min_p) * Decimal("100")).quantize(Decimal("0.01"))
        else:
            spread = Decimal("0.00")

        latest_query = (
            select(PriceHistory.created_at)
            .where(func.lower(PriceHistory.item_name) == normalized_item_name)
            .order_by(desc(PriceHistory.created_at))
            .limit(1)
        )
        latest_res = await self._session.execute(latest_query)
        latest_timestamp = latest_res.scalar() or datetime.now(timezone.utc)

        estimate = MarketPriceEstimate(
            item_name=item_name.strip(),
            sample_size=sample_size,
            min_price=min_p.quantize(Decimal("0.01")),
            max_price=max_p.quantize(Decimal("0.01")),
            average_price=avg_p.quantize(Decimal("0.01")),
            median_price=median_p.quantize(Decimal("0.01")),
            recommended_retail_price=rrp,
            currency="UZS",
            price_spread_percentage=spread,
            last_updated=latest_timestamp,
        )

        # 3. Cache result in Redis (TTL 3600 seconds = 1 hour)
        if self._redis is not None:
            try:
                await self._redis.set(
                    cache_key,
                    estimate.model_dump_json(),
                    ex=3600,
                )
            except Exception as exc:
                logger.debug("Redis cache set error for %s: %s", cache_key, exc)

        return estimate

    @staticmethod
    def _remove_outliers_iqr(sorted_prices: List[Decimal]) -> List[Decimal]:
        """Interquartile range (IQR) anomaly filter for skewed pricing reports."""
        n = len(sorted_prices)
        if n < 4:
            return sorted_prices

        q1_index = int(math.floor(n * 0.25))
        q3_index = int(math.floor(n * 0.75))

        q1 = sorted_prices[q1_index]
        q3 = sorted_prices[q3_index]
        iqr = q3 - q1

        lower_bound = q1 - (Decimal("1.5") * iqr)
        upper_bound = q3 + (Decimal("1.5") * iqr)

        filtered = [p for p in sorted_prices if lower_bound <= p <= upper_bound]
        return filtered if filtered else sorted_prices

    @staticmethod
    def _calculate_median(sorted_prices: List[Decimal]) -> Decimal:
        """Calculates exact median of a sorted list of decimal prices."""
        n = len(sorted_prices)
        mid = n // 2
        if n % 2 == 1:
            return sorted_prices[mid]
        return ((sorted_prices[mid - 1] + sorted_prices[mid]) / Decimal("2")).quantize(Decimal("0.01"))

    async def record_price(
        self,
        item_name: str,
        price: Decimal,
        market_name: str,
        reporter_id: Optional[int] = None,
    ) -> None:
        """Records a new observed price in the database and invalidates item cache."""
        if price <= Decimal("0"):
            raise ValueError("Цена должна быть строго положительным числом.")

        from database.models import PriceHistory

        entry = PriceHistory(
            item_name=item_name.strip().lower(),
            price=price,
            market_name=market_name.strip(),
            reporter_id=reporter_id,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(entry)
        await self._session.commit()
        logger.info(
            "Зафиксирована цена: товар='%s', цена=%s, рынок='%s', пользователь=%s",
            item_name, price, market_name, reporter_id,
        )

        # Invalidate cached estimate
        if self._redis is not None:
            try:
                normalized = item_name.strip().lower()
                pattern = f"market:estimate:{normalized}:*"
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
            except Exception as exc:
                logger.debug("Error invalidating cache for %s: %s", item_name, exc)

    @staticmethod
    def find_product_info(item_name: str) -> Optional[dict[str, Any]]:
        """Look up known price data for a product in Guliston static catalog."""
        query = item_name.strip().lower()
        for key, data in GULISTON_MARKET_INDEX.items():
            if key in query or query in key:
                res = data.copy()
                res["item_name"] = key.capitalize()
                return res
        return None

    @classmethod
    def analyze_shopping_list(cls, items: list[str]) -> dict[str, Any]:
        """
        Analyze an entire shopping list and divide it into:
        - What to buy at Guliston Dehqon Bozori
        - What to buy at Korzinka Guliston
        - Estimated total savings in UZS
        """
        bazaar_items: list[dict[str, Any]] = []
        supermarket_items: list[dict[str, Any]] = []
        unmatched_items: list[str] = []

        total_bazaar_est = 0
        total_supermarket_est = 0
        total_savings = 0

        for raw_item in items:
            info = cls.find_product_info(raw_item)
            if info:
                b_price = info["bazaar_price"]
                s_price = info["supermarket_price"]
                best = info["best_place"]

                item_entry = {
                    "name": raw_item,
                    "matched_as": info["item_name"],
                    "bazaar_price": b_price,
                    "supermarket_price": s_price,
                    "unit": info["unit"],
                    "tip": info["recommendation"],
                }

                if best == "bazaar":
                    bazaar_items.append(item_entry)
                    total_bazaar_est += b_price
                    total_savings += max(0, s_price - b_price)
                else:
                    supermarket_items.append(item_entry)
                    total_supermarket_est += s_price
                    total_savings += max(0, b_price - s_price)
            else:
                unmatched_items.append(raw_item)

        total_cart = total_bazaar_est + total_supermarket_est

        return {
            "city": "Гулистан, Сырдарья",
            "currency": "UZS",
            "bazaar": {
                "name": "Гулистон Деҳқон Бозори",
                "items": bazaar_items,
                "count": len(bazaar_items),
                "estimated_subtotal": total_bazaar_est,
            },
            "supermarket": {
                "name": "Корзинка Гулистан (ул. Сайхун)",
                "items": supermarket_items,
                "count": len(supermarket_items),
                "estimated_subtotal": total_supermarket_est,
            },
            "other_items": unmatched_items,
            "total_estimated": total_cart,
            "estimated_savings": total_savings,
            "summary_advice": (
                f"Разделив покупки между Деҳқон Бозори и Корзинкой, вы сэкономите "
                f"примерно {total_savings:,.0f} сум. Свежее мясо и овощи берите на базаре, "
                f"а бакалею, масла и бытовую химию — в Корзинке."
                if total_savings > 0
                else "Оптимальный маршрут составлен с учетом текущих цен в Гулистане."
            ),
        }

    @classmethod
    def get_plov_calculator(cls, servings: int = 6) -> dict[str, Any]:
        """Calculates exact ingredients and prices for Osh/Plov in Guliston."""
        scale = servings / 6.0
        meat_kg = 1.0 * scale
        rice_kg = 1.0 * scale
        carrot_kg = 1.0 * scale
        onion_kg = 0.4 * scale
        oil_l = 0.3 * scale

        meat_cost = int(meat_kg * 90000)
        rice_cost = int(rice_kg * 26000)
        carrot_cost = int(carrot_kg * 3000)
        onion_cost = int(onion_kg * 2500)
        oil_cost = int(oil_l * 18500)

        total = meat_cost + rice_cost + carrot_cost + onion_cost + oil_cost

        return {
            "dish": "Ташкентский / Сырдарьинский Плов",
            "servings": servings,
            "ingredients": [
                {"name": "Говядина (мякоть + косточка)", "amount": f"{meat_kg:.1f} кг", "cost": meat_cost, "where": "Деҳқон Бозори"},
                {"name": "Рис Лазер (отборный)", "amount": f"{rice_kg:.1f} кг", "cost": rice_cost, "where": "Деҳқон Бозори"},
                {"name": "Морковь желтая + красная", "amount": f"{carrot_kg:.1f} кг", "cost": carrot_cost, "where": "Деҳқон Бозори"},
                {"name": "Лук репчатый", "amount": f"{onion_kg:.1f} кг", "cost": onion_cost, "where": "Деҳқон Бозори"},
                {"name": "Масло растительное/пахта", "amount": f"{oil_l:.2f} л", "cost": oil_cost, "where": "Корзинка Гулистан"},
            ],
            "total_uzs": total,
            "per_person_uzs": int(total / max(1, servings)),
        }
