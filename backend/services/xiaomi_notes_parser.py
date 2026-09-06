"""
OmniCart AI — Xiaomi Notes (Mi Notes) Parser Service.
Parses checklists, text exports, and shopping lists copied from Xiaomi Notes.
Extracts items, units, quantities, prices, and identifies recurrent household staples.
"""

from __future__ import annotations

import re
from typing import Any


# Common household staples frequently bought in Uzbekistan households
RECURRENT_STAPLES = {
    "хлеб": {"category": "bakery", "typical_qty": 2, "unit": "шт", "frequency_days": 2},
    "лепешка": {"category": "bakery", "typical_qty": 3, "unit": "шт", "frequency_days": 2},
    "патыр": {"category": "bakery", "typical_qty": 1, "unit": "шт", "frequency_days": 3},
    "молоко": {"category": "dairy", "typical_qty": 1, "unit": "л", "frequency_days": 3},
    "яйца": {"category": "dairy", "typical_qty": 10, "unit": "шт", "frequency_days": 5},
    "масло": {"category": "grocery", "typical_qty": 1, "unit": "л", "frequency_days": 7},
    "подсолнечное масло": {"category": "grocery", "typical_qty": 1, "unit": "л", "frequency_days": 10},
    "картофель": {"category": "produce", "typical_qty": 3, "unit": "кг", "frequency_days": 5},
    "картошка": {"category": "produce", "typical_qty": 3, "unit": "кг", "frequency_days": 5},
    "лук": {"category": "produce", "typical_qty": 2, "unit": "кг", "frequency_days": 5},
    "морковь": {"category": "produce", "typical_qty": 1.5, "unit": "кг", "frequency_days": 5},
    "говядина": {"category": "meat", "typical_qty": 1.5, "unit": "кг", "frequency_days": 7},
    "мясо": {"category": "meat", "typical_qty": 1.5, "unit": "кг", "frequency_days": 7},
    "курица": {"category": "meat", "typical_qty": 1, "unit": "кг", "frequency_days": 5},
    "рис": {"category": "grocery", "typical_qty": 2, "unit": "кг", "frequency_days": 7},
    "сахар": {"category": "grocery", "typical_qty": 1, "unit": "кг", "frequency_days": 10},
    "чай": {"category": "grocery", "typical_qty": 1, "unit": "пачка", "frequency_days": 14},
    "мука": {"category": "grocery", "typical_qty": 2, "unit": "кг", "frequency_days": 10},
    "порошок": {"category": "household", "typical_qty": 1, "unit": "шт", "frequency_days": 20},
    "мыло": {"category": "household", "typical_qty": 2, "unit": "шт", "frequency_days": 15},
}


class XiaomiNotesParser:
    """Parses text exported or copied from Xiaomi Notes."""

    # Regex patterns for stripping Xiaomi checklist markers
    CHECKBOX_PREFIX = re.compile(r"^\s*(?:[-*+]\s*\[[ xX]?\]|\[[ xX]?\]|[-*•–—]|\d+[.)])\s*")
    PRICE_PATTERN = re.compile(
        r"(?:по\s*|за\s*|-|=)?\s*(\d+[\d\s.,]*)\s*(?:сум|som|so'm|uzs|руб|т)?",
        re.IGNORECASE,
    )
    QTY_UNIT_PATTERN = re.compile(
        r"(\d+(?:[.,]\d+)?)\s*(кг|kg|кило|г|g|грамм|литр|л|l|шт|штук|упак|пачк|бут|бутылк|пакет|пуч|пучок)\b",
        re.IGNORECASE,
    )

    @classmethod
    def parse_note_text(cls, text: str) -> list[dict[str, Any]]:
        """
        Parses multi-line Xiaomi Notes text into clean structured items.
        Handles checkbox states, amounts, and prices.
        """
        lines = text.strip().splitlines()
        parsed_items: list[dict[str, Any]] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Detect if item was already checked in Xiaomi Notes (e.g. [x] or [X] or strikethrough)
            is_checked = bool(re.match(r"^\s*(?:[-*+]\s*\[[xX]\]|\[[xX]\]|~~)", line))

            # Strip checkboxes, bullets, numbers, strikethrough
            cleaned = cls.CHECKBOX_PREFIX.sub("", line)
            cleaned = cleaned.replace("~~", "").strip()

            if not cleaned or len(cleaned) < 2:
                continue

            # Extract Quantity and Unit if present
            quantity = 1.0
            unit = "шт"
            qty_match = cls.QTY_UNIT_PATTERN.search(cleaned)
            if qty_match:
                try:
                    qty_str = qty_match.group(1).replace(",", ".")
                    quantity = float(qty_str)
                    raw_unit = qty_match.group(2).lower()
                    if raw_unit in ("кг", "kg", "кило"):
                        unit = "кг"
                    elif raw_unit in ("л", "l", "литр"):
                        unit = "л"
                    elif raw_unit in ("г", "g", "грамм"):
                        quantity = quantity / 1000.0
                        unit = "кг"
                    elif raw_unit in ("пачк", "пачка"):
                        unit = "пачка"
                    elif raw_unit in ("бут", "бутылк"):
                        unit = "бутылка"
                    elif raw_unit in ("пуч", "пучок"):
                        unit = "пучок"
                    else:
                        unit = "шт"
                except Exception:
                    quantity = 1.0

            # Extract Price if mentioned (e.g. "Картошка 3кг по 4500" or "Мясо 1кг - 90000 сум")
            price = 0.0
            price_match = cls.PRICE_PATTERN.search(cleaned)
            if price_match:
                try:
                    p_str = price_match.group(1).replace(" ", "").replace(",", ".")
                    val = float(p_str)
                    if val > 100:  # Sensible minimum in UZS
                        price = val
                except Exception:
                    price = 0.0

            # Clean up the product name
            name = cleaned
            if qty_match:
                name = name[: qty_match.start()] + " " + name[qty_match.end() :]
            if price_match:
                name = name[: price_match.start()] + " " + name[price_match.end() :]

            # Clean extra punctuation
            name = re.sub(r"[,:;—\-=\(\)]", " ", name)
            name = re.sub(r"\s+", " ", name).strip()
            if not name:
                name = cleaned

            # Determine if this is a recurring staple
            is_staple = False
            staple_info = None
            for staple_key, s_data in RECURRENT_STAPLES.items():
                if staple_key in name.lower():
                    is_staple = True
                    staple_info = s_data
                    break

            parsed_items.append(
                {
                    "item_name": name.capitalize(),
                    "quantity": quantity,
                    "unit": unit,
                    "estimated_price": price,
                    "is_purchased": is_checked,
                    "is_recurrent_staple": is_staple,
                    "category": staple_info["category"] if staple_info else "general",
                }
            )

        return parsed_items

    @classmethod
    def generate_replenishment_checklist(
        cls, history_items: list[str]
    ) -> list[dict[str, Any]]:
        """
        Generates a recommended checklist of regular household staples
        based on frequently purchased items.
        """
        recommendations: list[dict[str, Any]] = []
        found_keys: set[str] = set()

        # Check existing history or staples
        for staple_name, data in RECURRENT_STAPLES.items():
            if staple_name not in found_keys:
                found_keys.add(staple_name)
                recommendations.append(
                    {
                        "item_name": staple_name.capitalize(),
                        "quantity": data["typical_qty"],
                        "unit": data["unit"],
                        "reason": f"Регулярная покупка для дома (каждые {data['frequency_days']} дн.)",
                        "category": data["category"],
                    }
                )

        return recommendations[:10]
