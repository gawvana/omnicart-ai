"""
OmniCart AI — Checklist (Shopping List) Router.
Handles CRUD operations, status toggling, and bulk clearing for personal and family shopping lists.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from api.deps import AuthUser, DBSession, _sanitize_string, get_or_create_user
from database.models import PurchaseHistory
from services.universal_ai_parser import UniversalAIParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/checklist", tags=["Checklist"])


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


@router.get("", response_model=list[ChecklistItemResponse])
async def get_checklist(
    tg_user: AuthUser,
    db: DBSession,
    include_purchased: bool = Query(False),
) -> list[ChecklistItemResponse]:
    """Retrieve all shopping list items for current user or shared family cart."""
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    query = select(PurchaseHistory).where(PurchaseHistory.user_id == cart_id)
    if not include_purchased:
        query = query.where(PurchaseHistory.is_purchased == False)  # noqa: E712
    query = query.order_by(
        PurchaseHistory.is_purchased.asc(),
        PurchaseHistory.category.asc(),
        PurchaseHistory.created_at.desc(),
    )

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


@router.post("", response_model=ChecklistItemResponse, status_code=201)
async def add_checklist_item(
    body: AddItemRequest,
    tg_user: AuthUser,
    db: DBSession,
) -> ChecklistItemResponse:
    """Add a new item to the shopping list."""
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


@router.patch("/{item_id}/toggle")
async def toggle_purchased(
    item_id: str,
    body: TogglePurchasedRequest,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Toggle purchased status of an item."""
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    try:
        uid = uuid.UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid item ID") from exc

    result = await db.execute(
        select(PurchaseHistory).where(
            PurchaseHistory.id == uid,
            PurchaseHistory.user_id.in_([user.id, cart_id]),
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


@router.delete("/{item_id}", status_code=200)
async def delete_checklist_item(
    item_id: str,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Remove an item from the shopping list."""
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    try:
        uid = uuid.UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid item ID") from exc

    result = await db.execute(
        select(PurchaseHistory).where(
            PurchaseHistory.id == uid,
            PurchaseHistory.user_id.in_([user.id, cart_id]),
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()
    return {"status": "deleted", "id": item_id}


@router.post("/clear-purchased")
async def clear_purchased_checklist_items(
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Purge all completed items from user or shared family cart."""
    user = await get_or_create_user(tg_user, db)
    cart_id = user.family_cart_id if user.family_cart_id else user.id

    result = await db.execute(
        delete(PurchaseHistory).where(
            PurchaseHistory.user_id.in_([user.id, cart_id]),
            PurchaseHistory.is_purchased == True,  # noqa: E712
        )
    )
    await db.commit()
    return {"status": "cleared", "deleted_count": result.rowcount or 0}
