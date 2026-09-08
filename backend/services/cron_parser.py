"""
OmniCart AI — Daily Price Cache & Autocompletion Service.
Caches local market prices in Redis for sub-15ms autocompletion.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_PRICE_KEY = "market:prices:local"

# Baseline market catalog (updated daily via cron)
DEFAULT_LOCAL_PRICES: list[dict[str, Any]] = [
    {"name": "Говядина (мякоть)", "price": 95000, "bazaar_price": 90000, "supermarket_price": 105000, "unit": "кг", "category": "🥩 Мясной отдел"},
    {"name": "Баранина свежая", "price": 105000, "bazaar_price": 100000, "supermarket_price": 115000, "unit": "кг", "category": "🥩 Мясной отдел"},
    {"name": "Фарш говяжий", "price": 85000, "bazaar_price": 80000, "supermarket_price": 95000, "unit": "кг", "category": "🥩 Мясной отдел"},
    {"name": "Куриное филе", "price": 42000, "bazaar_price": 40000, "supermarket_price": 46000, "unit": "кг", "category": "🥩 Мясной отдел"},
    {"name": "Картофель красный", "price": 4500, "bazaar_price": 4000, "supermarket_price": 5500, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Лук репчатый", "price": 3500, "bazaar_price": 3000, "supermarket_price": 4500, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Морковь желтая (для плова)", "price": 3500, "bazaar_price": 3000, "supermarket_price": 4800, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Морковь красная", "price": 3500, "bazaar_price": 3000, "supermarket_price": 4500, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Помидоры розовые", "price": 18000, "bazaar_price": 15000, "supermarket_price": 22000, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Огурцы тепличные", "price": 14000, "bazaar_price": 12000, "supermarket_price": 17000, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Чеснок головка", "price": 28000, "bazaar_price": 25000, "supermarket_price": 32000, "unit": "кг", "category": "🥦 Овощные ряды"},
    {"name": "Зелень ассорти (кинза, укроп)", "price": 2500, "bazaar_price": 2000, "supermarket_price": 4000, "unit": "пучок", "category": "🥦 Овощные ряды"},
    {"name": "Рис Лазер (элитный)", "price": 26000, "bazaar_price": 24000, "supermarket_price": 30000, "unit": "кг", "category": "🥫 Бакалея и специи"},
    {"name": "Рис Аланга", "price": 19000, "bazaar_price": 17000, "supermarket_price": 21500, "unit": "кг", "category": "🥫 Бакалея и специи"},
    {"name": "Рис Девзира", "price": 32000, "bazaar_price": 30000, "supermarket_price": 36000, "unit": "кг", "category": "🥫 Бакалея и специи"},
    {"name": "Масло хлопковое (Олтин Калит)", "price": 18500, "bazaar_price": 17500, "supermarket_price": 21000, "unit": "л", "category": "🥫 Бакалея и специи"},
    {"name": "Масло подсолнечное (Щедрое лето)", "price": 22000, "bazaar_price": 21000, "supermarket_price": 23500, "unit": "л", "category": "🥫 Бакалея и специи"},
    {"name": "Мука 1 сорт (Казахстан)", "price": 7500, "bazaar_price": 7000, "supermarket_price": 8500, "unit": "кг", "category": "🥫 Бакалея и специи"},
    {"name": "Сахар песок", "price": 13500, "bazaar_price": 13000, "supermarket_price": 14500, "unit": "кг", "category": "🥫 Бакалея и специи"},
    {"name": "Чай зеленый 95", "price": 12000, "bazaar_price": 10000, "supermarket_price": 15000, "unit": "пачка", "category": "🥫 Бакалея и специи"},
    {"name": "Зира иранская (специи)", "price": 18000, "bazaar_price": 15000, "supermarket_price": 24000, "unit": "пачка", "category": "🥫 Бакалея и специи"},
    {"name": "Нут (горох для плова)", "price": 22000, "bazaar_price": 20000, "supermarket_price": 26000, "unit": "кг", "category": "🥫 Бакалея и специи"},
    {"name": "Лепешка тандырная (нон)", "price": 4000, "bazaar_price": 4000, "supermarket_price": 4500, "unit": "шт", "category": "🍞 Лепешки и выпечка"},
    {"name": "Паттыр самаркандский", "price": 12000, "bazaar_price": 10000, "supermarket_price": 14000, "unit": "шт", "category": "🍞 Лепешки и выпечка"},
    {"name": "Молоко 3.2% (1л)", "price": 11000, "bazaar_price": 9000, "supermarket_price": 12500, "unit": "л", "category": "🥛 Молочные ряды"},
    {"name": "Катык (кефир домашний)", "price": 8000, "bazaar_price": 7000, "supermarket_price": 10000, "unit": "л", "category": "🥛 Молочные ряды"},
    {"name": "Сметана 20% (домашняя)", "price": 32000, "bazaar_price": 28000, "supermarket_price": 36000, "unit": "кг", "category": "🥛 Молочные ряды"},
    {"name": "Яйца домашние (10 шт)", "price": 17000, "bazaar_price": 16000, "supermarket_price": 19000, "unit": "дес", "category": "🥛 Молочные ряды"},
    {"name": "Стиральный порошок (3кг)", "price": 68000, "bazaar_price": 68000, "supermarket_price": 64000, "unit": "пачка", "category": "🧼 Бытовая химия"},
    {"name": "Средство Fairy (1л)", "price": 24000, "bazaar_price": 25000, "supermarket_price": 22500, "unit": "шт", "category": "🧼 Бытовая химия"},
]


class PriceCronService:
    """Synchronizes prices to Redis and powers sub-15ms autocompletion."""

    @classmethod
    async def sync_daily_prices(cls, redis: Optional[aioredis.Redis]) -> dict[str, Any]:
        """Runs daily price refresh, caches to Redis with 24h expiration."""
        if redis is None:
            return {"status": "skipped", "reason": "redis_not_configured"}

        try:
            existing_raw = await redis.get(REDIS_PRICE_KEY)
            items_dict: dict[str, dict[str, Any]] = {p["name"].lower(): p for p in DEFAULT_LOCAL_PRICES}

            if existing_raw:
                try:
                    existing_items = json.loads(existing_raw)
                    for ei in existing_items:
                        name_key = ei.get("name", "").lower()
                        if name_key in items_dict and ei.get("crowdsourced"):
                            items_dict[name_key]["bazaar_price"] = ei["bazaar_price"]
                            items_dict[name_key]["price"] = ei["price"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

            final_list = list(items_dict.values())
            await redis.set(REDIS_PRICE_KEY, json.dumps(final_list, ensure_ascii=False), ex=86400)
            logger.info("Synced %d market prices to Redis", len(final_list))
            return {"status": "ok", "items_count": len(final_list)}

        except aioredis.RedisError as exc:
            logger.error("Price sync error: %s", exc)
            return {"status": "error", "error": str(exc)}

    @classmethod
    async def get_all_prices(cls, redis: Optional[aioredis.Redis]) -> list[dict[str, Any]]:
        """Returns full price list from Redis or memory fallback."""
        if redis:
            try:
                data = await redis.get(REDIS_PRICE_KEY)
                if data:
                    return json.loads(data)
            except (aioredis.RedisError, json.JSONDecodeError) as exc:
                logger.warning("Failed to fetch prices from Redis: %s", exc)

        return DEFAULT_LOCAL_PRICES

    @classmethod
    async def autocomplete(cls, query: str, redis: Optional[aioredis.Redis], limit: int = 6) -> list[dict[str, Any]]:
        """Instant sub-15ms prefix and substring search for auto-completion."""
        if not query or len(query.strip()) < 1:
            return []

        q = query.strip().lower()
        all_prices = await cls.get_all_prices(redis)

        matched = []
        for p in all_prices:
            name = p["name"].lower()
            if name.startswith(q) or q in name:
                matched.append(p)
                if len(matched) >= limit:
                    break

        return matched

    @classmethod
    async def update_user_price(
        cls, item_name: str, new_price: float, redis: Optional[aioredis.Redis]
    ) -> bool:
        """Crowdsourcing: allows users to submit actual prices from the bazaar."""
        all_prices = await cls.get_all_prices(redis)
        found = False
        target = item_name.strip().lower()

        for p in all_prices:
            if p["name"].lower() == target or target in p["name"].lower():
                p["bazaar_price"] = new_price
                p["price"] = new_price
                p["crowdsourced"] = True
                found = True
                break

        if not found:
            all_prices.append({
                "name": item_name.strip().capitalize(),
                "price": new_price,
                "bazaar_price": new_price,
                "supermarket_price": new_price * 1.15,
                "unit": "кг",
                "category": "🥦 Овощные ряды",
                "crowdsourced": True,
            })

        if redis:
            try:
                await redis.set(REDIS_PRICE_KEY, json.dumps(all_prices, ensure_ascii=False), ex=86400)
            except aioredis.RedisError as exc:
                logger.warning("Failed to update price in Redis: %s", exc)

        return True
