"""
OmniCart AI — Family Cart Router.
Manages shared family shopping cart memberships and permissions.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import AuthUser, DBSession, get_or_create_user
from database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cart", tags=["Family Cart"])


class JoinFamilyBody(BaseModel):
    family_cart_id: str


@router.post("/join-family")
async def join_family_cart(
    body: JoinFamilyBody,
    tg_user: AuthUser,
    db: DBSession,
) -> dict[str, Any]:
    """Join another user's family cart for shared real-time shopping."""
    user = await get_or_create_user(tg_user, db)

    try:
        target_uuid = uuid.UUID(body.family_cart_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid family cart UUID format") from exc

    # Security check: verify that target cart / owner exists
    result = await db.execute(select(User).where(User.id == target_uuid))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="Family cart not found")

    user.family_cart_id = target_uuid
    await db.commit()
    logger.info("User %s joined family cart %s", user.id, target_uuid)

    return {"status": "joined", "family_cart_id": str(target_uuid)}
