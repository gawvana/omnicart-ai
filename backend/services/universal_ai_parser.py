"""
OmniCart AI — Universal AI Parser (DeepSeek / B.AI powered).
Replaces brittle regex scripts with an intelligent natural language understanding engine.
Handles:
- Any messy copied text / Xiaomi Notes / iPhone notes
- Voice-to-text transcriptions
- Recipe reversal (extracting scaled ingredients)
- Auto-tagging into standard bazaar aisles
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

from services.b_ai_client import BAIClient, BAIClientError

logger = logging.getLogger(__name__)

# Standard bazaar aisles
BAZAAR_CATEGORIES = [
    "🥩 Мясной отдел",
    "🥦 Овощные ряды",
    "🥛 Молочные ряды",
    "🍞 Лепешки и выпечка",
    "🥫 Бакалея и специи",
    "🧼 Бытовая химия",
]


class ParsedItem(BaseModel):
    name: str = Field(..., description="Название товара")
    qty: float = Field(default=1.0, description="Количество")
    unit: str = Field(default="кг", description="Единица измерения (кг, л, шт, пачка)")
    category: str = Field(default="🥫 Бакалея и специи", description="Ряд или отдел базара")
    estimated_price: float = Field(default=0.0, description="Ориентировочная цена в UZS (сум)")


class UniversalParseResult(BaseModel):
    items: list[ParsedItem] = Field(default_factory=list)
    source_type: str = "text"
    summary: str = ""


class UniversalAIParser:
    """
    Central AI engine for parsing free text, notes, voice transcripts, and recipes.
    """

    @staticmethod
    def _categorize_fallback(name: str) -> str:
        """Heuristic fallback category tagger for fast offline / failover."""
        n = name.lower()
        if any(w in n for w in ["мясо", "говядина", "баранина", "фарш", "курица", "филе", "конина", "казы", "ребрышки", "гушт", "go'sht"]):
            return "🥩 Мясной отдел"
        if any(w in n for w in ["помидор", "огурец", "картошк", "картофель", "лук", "морков", "зелень", "укроп", "петрушк", "кинза", "чеснок", "яблок", "банан", "лимон", "капуст", "перец", "баклажан", "пиёз", "sabzi", "kartoshka"]):
            return "🥦 Овощные ряды"
        if any(w in n for w in ["молоко", "кефир", "катык", "сметана", "творог", "сыр", "сливочное масло", "йогурт", "сут", "qatiq"]):
            return "🥛 Молочные ряды"
        if any(w in n for w in ["лепешк", "хлеб", "нон", "буханка", "самса", "лаваш", "булочк"]):
            return "🍞 Лепешки и выпечка"
        if any(w in n for w in ["мыло", "порошок", "шампунь", "паста", "бумага", "салфетк", "fairy", "губка", "пакет"]):
            return "🧼 Бытовая химия"
        return "🥫 Бакалея и специи"

    @classmethod
    async def parse_any_text(cls, text: str) -> UniversalParseResult:
        """
        Parses any text input (Xiaomi notes, natural messages, voice transcriptions)
        into a structured list of shopping items.
        """
        if not text or not text.strip():
            return UniversalParseResult(items=[])

        prompt = (
            "Ты — интеллектуальный ассистент покупок для базара и магазинов Узбекистана (г. Гулистан).\n"
            "Пользователь отправил текст (это может быть скопированная заметка Xiaomi Notes, чек-лист, "
            "голосовое сообщение или список покупок).\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Извлечь ВСЕ упомянутые продукты и товары.\n"
            "2. Очистить от любых чекбоксов, значков вроде [ ], [x], •, -, тире, номеров.\n"
            "3. Определить точное количество (qty) и единицу измерения (unit: кг, л, шт, пачка, буханка).\n"
            "4. Определить ряд/категорию базара строго из списка:\n"
            "   - '🥩 Мясной отдел'\n"
            "   - '🥦 Овощные ряды'\n"
            "   - '🥛 Молочные ряды'\n"
            "   - '🍞 Лепешки и выпечка'\n"
            "   - '🥫 Бакалея и специи'\n"
            "   - '🧼 Бытовая химия'\n"
            "5. Если в тексте указана цена (в сумах / сум / UZS / k), извлечь её в estimated_price как число. Если нет, оставь 0.\n\n"
            "ВЕРНИ СТРОГО ВАЛИДНЫЙ JSON-МАССИВ ОБЪЕКТОВ без markdown-оберток:\n"
            '[\n'
            '  {"name": "Говядина", "qty": 1.5, "unit": "кг", "category": "🥩 Мясной отдел", "estimated_price": 135000},\n'
            '  {"name": "Лепешки", "qty": 2.0, "unit": "шт", "category": "🍞 Лепешки и выпечка", "estimated_price": 8000}\n'
            ']'
        )

        try:
            async with BAIClient() as client:
                raw_response = await client._chat_completion(
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text[:3000]},
                    ],
                    temperature=0.1,
                    max_tokens=1500,
                )
                clean_json = client._extract_json(raw_response)
                data = json.loads(clean_json)

                if isinstance(data, list):
                    items = []
                    for it in data:
                        cat = it.get("category")
                        if not cat or cat not in BAZAAR_CATEGORIES:
                            cat = cls._categorize_fallback(it.get("name", ""))
                        items.append(
                            ParsedItem(
                                name=str(it.get("name", "")).strip().capitalize()[:100],
                                qty=float(it.get("qty", 1.0)),
                                unit=str(it.get("unit", "кг"))[:20],
                                category=cat,
                                estimated_price=float(it.get("estimated_price", 0.0)),
                            )
                        )
                    return UniversalParseResult(items=items, source_type="ai_parsed")

        except Exception as exc:
            logger.warning("UniversalAIParser AI parsing failed: %s. Using heuristic parser.", exc)

        # Heuristic fast fallback if AI fails or rate limits
        return cls._fallback_parse(text)

    @classmethod
    async def parse_recipe(cls, recipe_text: str, servings: int = 4) -> UniversalParseResult:
        """
        Reverse recipe analysis: extracts ingredients and scales quantities for N servings.
        """
        prompt = (
            f"Ты — шеф-повар и эксперт по закупкам. Проанализируй текст или рецепт и составь точный список продуктов "
            f"для закупки на базаре для {servings} персон.\n\n"
            "ВЕРНИ СТРОГО JSON-МАССИВ ОБЪЕКТОВ:\n"
            '[\n'
            '  {"name": "Мясо говядина", "qty": 0.8, "unit": "кг", "category": "🥩 Мясной отдел", "estimated_price": 75000}\n'
            ']'
        )

        try:
            async with BAIClient() as client:
                raw_resp = await client._chat_completion(
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": recipe_text[:3500]},
                    ],
                    temperature=0.2,
                )
                clean_json = client._extract_json(raw_resp)
                data = json.loads(clean_json)
                if isinstance(data, list):
                    items = [
                        ParsedItem(
                            name=str(it.get("name", "")).strip().capitalize()[:100],
                            qty=float(it.get("qty", 1.0)),
                            unit=str(it.get("unit", "кг"))[:20],
                            category=it.get("category") or cls._categorize_fallback(it.get("name", "")),
                            estimated_price=float(it.get("estimated_price", 0.0)),
                        )
                        for it in data
                    ]
                    return UniversalParseResult(items=items, source_type="recipe", summary=f"Ингредиенты на {servings} чел.")
        except Exception as exc:
            logger.error("Recipe parse error: %s", exc)

        return cls._fallback_parse(recipe_text)

    @classmethod
    def _fallback_parse(cls, text: str) -> UniversalParseResult:
        """Instant heuristic fallback parser without external API calls."""
        raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
        lines: list[str] = []
        for rl in raw_lines:
            # Split comma-separated items if present e.g. "картошка 2кг, мясо 1кг"
            if "," in rl or ";" in rl:
                parts = [p.strip() for p in re.split(r"[,;]+", rl) if p.strip()]
                lines.extend(parts)
            else:
                lines.append(rl)

        items: list[ParsedItem] = []
        for line in lines[:50]:
            cleaned = re.sub(r"^[-*•\d\.\)\[\]xX\s]+", "", line).strip()
            if not cleaned or len(cleaned) < 2:
                continue

            # 1. Extract price if present (e.g. "50000 сум", "50 000 uzs", or trailing number >= 500)
            price = 0.0
            price_match = re.search(r"(\d+[\d\s]*)\s*(?:сум|sum|uzs)\b", cleaned, re.IGNORECASE)
            if not price_match:
                price_match = re.search(r"\s+(\d{3,}(?:[\s\d]*))\s*$", cleaned)
            if price_match:
                try:
                    price = float(price_match.group(1).replace(" ", ""))
                except ValueError:
                    pass
                cleaned = (cleaned[:price_match.start()] + " " + cleaned[price_match.end():]).strip()

            # 2. Extract qty and unit
            qty = 1.0
            unit = "шт"
            qty_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(кг|г|л|литр|шт|пачк\w*|буханк\w*|упак\w*)", cleaned, re.IGNORECASE)
            if qty_match:
                try:
                    qty = float(qty_match.group(1).replace(",", "."))
                    raw_u = qty_match.group(2).lower()
                    if raw_u.startswith("кг"):
                        unit = "кг"
                    elif raw_u.startswith("г"):
                        unit = "г"
                    elif raw_u.startswith("л"):
                        unit = "л"
                    elif raw_u.startswith("пачк") or raw_u.startswith("упак"):
                        unit = "упак"
                    else:
                        unit = "шт"
                except ValueError:
                    pass
                cleaned = (cleaned[:qty_match.start()] + " " + cleaned[qty_match.end():]).strip()

            name = re.sub(r"[^\w\sа-яА-ЯёЁўқғҳЎҚҒҲa-zA-Z]", "", cleaned).strip()
            if name:
                items.append(
                    ParsedItem(
                        name=name.capitalize()[:100],
                        qty=qty,
                        unit=unit,
                        category=cls._categorize_fallback(name),
                        estimated_price=price,
                    )
                )

        return UniversalParseResult(items=items, source_type="heuristic")
