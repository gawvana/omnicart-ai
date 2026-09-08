"""
OmniCart AI — User Profile and Settings Router.
Manages user preferences, localization, and spending summaries.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.deps import AuthUser, DBSession, _sanitize_string, get_or_create_user
from database.models import PurchaseHistory, UserSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["User"])


class SettingsUpdateRequest(BaseModel):
    country_code: Optional[str] = Field(None, max_length=3)
    city: Optional[str] = Field(None, max_length=255)
    currency_code: Optional[str] = Field(None, max_length=3)
    measurement_system: Optional[str] = Field(None, pattern=r"^(metric|imperial)$")
    dietary_preferences: Optional[dict[str, bool]] = None
    monthly_budget: Optional[Decimal] = Field(None, ge=0)
    timezone: Optional[str] = Field(None, max_length=50)
    shopping_culture: Optional[str] = Field(None, pattern=r"^(bazaar|supermarket|mixed)$")


class UserProfileResponse(BaseModel):
    user_id: str
    first_name: Optional[str]
    settings: dict[str, Any]
    total_items: int
    total_spent: str


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(tg_user: AuthUser, db: DBSession) -> UserProfileResponse:
    """Fetch user profile with aggregate stats and settings."""
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


@router.put("/settings")
@router.patch("/settings")
async def update_settings(
    body: SettingsUpdateRequest,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, str]:
    """Update user configuration and shopping preferences."""
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
