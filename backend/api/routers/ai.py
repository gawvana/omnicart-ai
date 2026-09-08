"""
OmniCart AI — AI Processing & Natural Language Parsing Router.
Powers smart recipe scaling, unstructured text parsing, notes import, and purchase extraction.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.deps import AuthUser, DBSession, _sanitize_string, get_bai, get_or_create_user
from database.models import LocalPriceIndex, PurchaseHistory
from services.b_ai_client import BAIClient, BAIClientError
from services.universal_ai_parser import UniversalAIParser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Processing"])


class UniversalParseBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


class RecipeParseBody(BaseModel):
    recipe: str = Field(..., min_length=1, max_length=20000)
    servings: int = Field(default=4, ge=1, le=50)


class XiaomiNotesImportBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


class PurchaseTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


@router.post("/api/v1/ai/parse-text")
async def parse_text_endpoint(
    body: UniversalParseBody,
    tg_user: AuthUser,
) -> dict[str, Any]:
    """Universal AI parser for any free text or copied shopping notes."""
    result = await UniversalAIParser.parse_any_text(body.text)
    return result.model_dump()


@router.post("/api/v1/ai/parse-recipe")
async def parse_recipe_endpoint(
    body: RecipeParseBody,
    tg_user: AuthUser,
) -> dict[str, Any]:
    """Recipe ingredient breakdown and automatic scaling for N servings."""
    result = await UniversalAIParser.parse_recipe(body.recipe, servings=body.servings)
    return result.model_dump()


@router.post("/api/v1/notes/import-xiaomi")
async def import_xiaomi_notes(
    body: XiaomiNotesImportBody,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Parse notes copied from notes apps and batch import into user checklist."""
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    parsed_result = await UniversalAIParser.parse_any_text(body.text)

    added: list[dict[str, Any]] = []
    for it in parsed_result.items:
        item = PurchaseHistory(
            user_id=cart_id,
            item_name=_sanitize_string(it.name),
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


@router.post("/api/v1/ai/parse-purchase")
async def ai_parse_purchase(
    body: PurchaseTextRequest,
    tg_user: AuthUser,
    db: DBSession,
    bai: Annotated[BAIClient, Depends(get_bai)],
) -> dict[str, Any]:
    """Parse shopping receipt or free text using B.AI LLM with user context."""
    user = await get_or_create_user(tg_user, db)
    user_settings = user.settings

    country = user_settings.country_code if user_settings else "UZ"
    city = user_settings.city if user_settings else "Гулистан"
    currency = user_settings.currency_code if user_settings else "UZS"
    measurement = user_settings.measurement_system if user_settings else "metric"
    culture = user_settings.shopping_culture if user_settings else "bazaar"
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


@router.get("/api/v1/ai/price-analysis")
async def ai_price_analysis(
    tg_user: AuthUser,
    db: DBSession,
    bai: Annotated[BAIClient, Depends(get_bai)],
) -> dict[str, Any]:
    """Analyze purchase history trends and price sanity."""
    user = await get_or_create_user(tg_user, db)
    user_settings = user.settings
    country = user_settings.country_code if user_settings else "UZ"
    city = user_settings.city if user_settings else "Гулистан"
    currency = user_settings.currency_code if user_settings else "UZS"

    purchases_result = await db.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.user_id == user.id)
        .order_by(PurchaseHistory.created_at.desc())
        .limit(50)
    )
    purchases = purchases_result.scalars().all()

    if not purchases:
        return {"analyses": [], "market_summary": "История покупок пуста."}

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
