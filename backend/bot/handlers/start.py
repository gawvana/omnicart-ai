"""
OmniCart AI — Telegram bot /start handler and core message dispatcher.
Registers the bot, processes text messages via B.AI, and launches the Mini App.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    WebAppInfo,
)
from aiogram.utils.markdown import hbold

from core.config import get_settings
from database.models import User, UserSettings, hash_telegram_id
from services.b_ai_client import BAIClient, BAIClientError

logger = logging.getLogger(__name__)

router = Router(name="start")

# ── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: types.Message, db_session: Any, bot: Bot) -> None:
    """Welcome message with Mini App launch button."""
    settings = get_settings()
    user = message.from_user
    if user is None:
        return

    tg_id_hash = hash_telegram_id(user.id)

    # Upsert user in DB
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = db_session
    result = await session.execute(
        select(User).where(User.telegram_id_hash == tg_id_hash)
    )
    db_user = result.scalar_one_or_none()

    if db_user is None:
        user_uuid = uuid.uuid4()
        db_user = User(
            id=user_uuid,
            telegram_id_hash=tg_id_hash,
            username=user.username[:255] if user.username else None,
            first_name=user.first_name[:255] if user.first_name else None,
            language_code=user.language_code[:10] if user.language_code else "en",
        )
        session.add(db_user)
        user_settings = UserSettings(id=uuid.uuid4(), user_id=user_uuid)
        session.add(user_settings)
        await session.commit()
        await session.refresh(db_user)
        logger.info("New user registered via /start: %s", db_user.id)
    else:
        if user.first_name and db_user.first_name != user.first_name[:255]:
            db_user.first_name = user.first_name[:255]
        if user.username and db_user.username != (user.username[:255] if user.username else None):
            db_user.username = user.username[:255] if user.username else None
        await session.commit()

    webapp_url = settings.telegram_webapp_url.rstrip("/")
    name = user.first_name or "there"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Open OmniCart",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="settings_menu",
                ),
                InlineKeyboardButton(
                    text="📊 Analytics",
                    callback_data="analytics_menu",
                ),
            ],
        ]
    )

    welcome_text = (
        f"👋 Hey {hbold(name)}! Welcome to {hbold('OmniCart AI')}\n\n"
        f"🧠 I'm your smart grocery assistant. I can:\n\n"
        f"  🛒  Manage your shopping list\n"
        f"  ✨  Parse purchases from natural text\n"
        f"  📈  Track spending & predict restocks\n"
        f"  💰  Compare local market prices\n\n"
        f"Tap the button below to open the app, or just send me a message "
        f"like:\n\n"
        f'  {hbold("bought 2kg potatoes for 500 at the bazaar")}\n\n'
        f"and I'll parse it automatically! 🚀"
    )

    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )

    # Set menu button to WebApp
    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(
                text="OmniCart",
                web_app=WebAppInfo(url=webapp_url),
            ),
        )
    except Exception as exc:
        logger.warning("Failed to set menu button: %s", exc)


# ── Free-text purchase parsing ───────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: types.Message, db_session: Any) -> None:
    """Parse free-text grocery messages via B.AI."""
    user = message.from_user
    text = message.text
    if user is None or not text:
        return

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from database.models import PurchaseHistory

    session: AsyncSession = db_session
    tg_id_hash = hash_telegram_id(user.id)

    result = await session.execute(
        select(User).where(User.telegram_id_hash == tg_id_hash)
    )
    db_user = result.scalar_one_or_none()
    if db_user is None:
        await message.answer("Please send /start first to register.")
        return

    user_settings = db_user.settings

    country = user_settings.country_code if user_settings else "US"
    city = user_settings.city if user_settings else "New York"
    currency = user_settings.currency_code if user_settings else "USD"
    measurement = user_settings.measurement_system if user_settings else "metric"
    culture = user_settings.shopping_culture if user_settings else "supermarket"
    dietary = user_settings.dietary_preferences if user_settings else None
    budget = user_settings.monthly_budget if user_settings else None

    processing_msg = await message.answer("✨ Parsing your purchase...")

    try:
        async with BAIClient() as client:
            parsed = await client.parse_purchase_text(
                text[:2000],
                country=country,
                city=city,
                currency=currency,
                measurement=measurement,
                shopping_culture=culture,
                dietary=dietary,
                budget=budget,
            )
    except BAIClientError as exc:
        logger.error("B.AI parse failed: %s", exc)
        await processing_msg.edit_text(
            "❌ Sorry, I couldn't parse that. Please try rephrasing or use the app."
        )
        return

    if not parsed.items:
        await processing_msg.edit_text(
            "🤔 I couldn't find any grocery items in your message. Try something like:\n\n"
            '"bought 2kg potatoes for 500, 1L milk for 200"'
        )
        return

    # Save to DB
    saved_count = 0
    for pi in parsed.items:
        import re
        clean_name = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", pi.item_name)[:255]
        purchase = PurchaseHistory(
            id=uuid.uuid4(),
            user_id=db_user.id,
            raw_input_text=text[:2000],
            item_name=clean_name,
            quantity=pi.quantity,
            unit=pi.unit,
            price_paid=pi.price,
            currency_code=pi.currency,
            store_name=pi.store_name[:255] if pi.store_name else None,
            country_code=country,
            city=city,
            is_purchased=False,
            ai_parsed_data=pi.model_dump(mode="json"),
        )
        session.add(purchase)
        saved_count += 1

    await session.commit()

    # Format response
    lines: list[str] = [f"✅ Added {hbold(str(saved_count))} item(s) to your list:\n"]
    for pi in parsed.items:
        qty = pi.quantity
        qty_str = f"{qty:.0f}" if qty == int(qty) else f"{qty:.2f}"
        price_str = f"{pi.price:.0f}" if pi.price == int(pi.price) else f"{pi.price:.2f}"
        store_str = f" @ {pi.store_name}" if pi.store_name else ""
        conf = int(pi.confidence * 100)
        lines.append(
            f"  • {hbold(pi.item_name)} — {qty_str} {pi.unit} "
            f"for {price_str} {pi.currency}{store_str} "
            f"({conf}% conf.)"
        )

    if parsed.raw_interpretation:
        lines.append(f"\n💡 {parsed.raw_interpretation}")

    await processing_msg.edit_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# ── Callback: Settings ──────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_menu")
async def settings_callback(callback: types.CallbackQuery) -> None:
    settings = get_settings()
    webapp_url = f"{settings.telegram_webapp_url.rstrip('/')}/settings"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Open Settings",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Back",
                    callback_data="back_to_main",
                )
            ],
        ]
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "⚙️ Configure your location, currency, dietary preferences, and budget in the app:",
        reply_markup=keyboard,
    )
    await callback.answer()


# ── Callback: Analytics ─────────────────────────────────────────────────────

@router.callback_query(F.data == "analytics_menu")
async def analytics_callback(callback: types.CallbackQuery) -> None:
    settings = get_settings()
    webapp_url = f"{settings.telegram_webapp_url.rstrip('/')}/analytics"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Open Analytics",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Back",
                    callback_data="back_to_main",
                )
            ],
        ]
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📊 View your spending analytics, price comparisons, and replenishment predictions:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, bot: Bot) -> None:
    """Return to main menu."""
    settings = get_settings()
    webapp_url = settings.telegram_webapp_url.rstrip("/")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Open OmniCart",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="settings_menu",
                ),
                InlineKeyboardButton(
                    text="📊 Analytics",
                    callback_data="analytics_menu",
                ),
            ],
        ]
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "🛒 OmniCart AI — your smart grocery assistant.\n\nSend me a text message to log purchases, or open the app:",
        reply_markup=keyboard,
    )
    await callback.answer()
