"""
OmniCart AI — Telegram Bot Handlers (Russian, iOS 26 Aesthetic).
Supports both Pure Telegram Bot Mode (interactive checklists, Xiaomi Notes import,
Guliston market advice) and Telegram Mini App (TMA).
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.markdown import hbold, hcode, hitalic
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from database.models import PurchaseHistory, User, UserSettings, hash_telegram_id
from services.b_ai_client import BAIClient, BAIClientError
from services.guliston_market_service import GulistonMarketService
from services.xiaomi_notes_parser import XiaomiNotesParser

logger = logging.getLogger(__name__)

router = Router(name="start")


# ── Persistent Main Menu Keyboard (Reply Keyboard) ───────────────────────────

def get_main_reply_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard for fast pure-bot actions."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Чек-лист покупок"),
                KeyboardButton(text="📝 Из Xiaomi Заметок"),
            ],
            [
                KeyboardButton(text="🏛 Корзинка vs Базар"),
                KeyboardButton(text="💡 Регулярные товары"),
            ],
            [
                KeyboardButton(text="🍲 Калькулятор плова"),
                KeyboardButton(text="🚀 Открыть Mini App", web_app=WebAppInfo(url=webapp_url)),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ── Helper: Get or Create DB User ───────────────────────────────────────────

async def get_or_create_user(session: AsyncSession, tg_user: types.User) -> User:
    tg_id_hash = hash_telegram_id(tg_user.id)
    result = await session.execute(
        select(User).where(User.telegram_id_hash == tg_id_hash)
    )
    db_user = result.scalar_one_or_none()

    if db_user is None:
        user_uuid = uuid.uuid4()
        db_user = User(
            id=user_uuid,
            telegram_id_hash=tg_id_hash,
            username=tg_user.username[:255] if tg_user.username else None,
            first_name=tg_user.first_name[:255] if tg_user.first_name else None,
            language_code="ru",
        )
        session.add(db_user)
        user_settings = UserSettings(
            id=uuid.uuid4(),
            user_id=user_uuid,
            country_code="UZ",
            city="Гулистан",
            currency_code="UZS",
            shopping_culture="mixed",
        )
        session.add(user_settings)
        await session.commit()
        await session.refresh(db_user)
        logger.info("New user registered via bot: %s", db_user.id)
    else:
        changed = False
        if tg_user.first_name and db_user.first_name != tg_user.first_name[:255]:
            db_user.first_name = tg_user.first_name[:255]
            changed = True
        if tg_user.username and db_user.username != (tg_user.username[:255] if tg_user.username else None):
            db_user.username = tg_user.username[:255] if tg_user.username else None
            changed = True
        if changed:
            await session.commit()

    return db_user


# ── Helper: Render Interactive Checklist in Chat ────────────────────────────

async def render_checklist_message(
    session: AsyncSession, user_id: uuid.UUID, webapp_url: str
) -> tuple[str, InlineKeyboardMarkup]:
    """Generates an in-chat interactive checklist with inline checkmark toggles."""
    result = await session.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.user_id == user_id)
        .order_by(PurchaseHistory.is_purchased.asc(), PurchaseHistory.created_at.desc())
        .limit(20)
    )
    items = result.scalars().all()

    if not items:
        text = (
            f"📋 {hbold('Ваш чек-лист пуст')}\n\n"
            f"Вы можете:\n"
            f"• Написать продукты сообщением (например: {hitalic('картошка 2кг, молоко 1л, масло')})\n"
            f"• Вставить список из {hbold('Заметок Xiaomi')}\n"
            f"• Добавить регулярные товары через кнопку ниже"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💡 Добавить регулярные товары",
                        callback_data="add_staples_quick",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🚀 Открыть Mini App",
                        web_app=WebAppInfo(url=webapp_url),
                    )
                ],
            ]
        )
        return text, kb

    pending_count = sum(1 for i in items if not i.is_purchased)
    purchased_count = len(items) - pending_count

    lines = [
        f"📋 {hbold('Список покупок (Гулистан)')}",
        f"Осталось: {hbold(str(pending_count))}  |  Куплено: {purchased_count}\n",
    ]

    inline_rows: list[list[InlineKeyboardButton]] = []

    for idx, item in enumerate(items[:12], 1):
        status_sym = "✓" if item.is_purchased else " "
        line_item = f"[{status_sym}] {item.item_name}"
        if item.quantity and item.quantity > 0:
            qty = item.quantity
            qty_str = f"{qty:.0f}" if qty == int(qty) else f"{qty:.1f}"
            line_item += f" — {qty_str} {item.unit}"
        if item.price_paid and item.price_paid > 0:
            line_item += f" (~{item.price_paid:,.0f} сум)"

        lines.append(f"{idx}. {line_item}")

        # Inline button toggle for each item
        btn_text = f"✓ {item.item_name[:14]}" if not item.is_purchased else f"↩ {item.item_name[:14]}"
        inline_rows.append(
            [
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"chk_toggle:{str(item.id)[:8]}",
                )
            ]
        )

    # Action buttons
    action_row = [
        InlineKeyboardButton(text="🏛 Где выгоднее?", callback_data="chk_market_advise"),
        InlineKeyboardButton(text="🗑 Очистить купленное", callback_data="chk_clear_done"),
    ]
    inline_rows.append(action_row)
    inline_rows.append(
        [
            InlineKeyboardButton(
                text="🚀 Открыть Mini App (iOS 26)",
                web_app=WebAppInfo(url=webapp_url),
            )
        ]
    )

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=inline_rows)


# ── /start Handler ───────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_session: Any, bot: Bot) -> None:
    """Sleek iOS 26 style Russian welcome handler."""
    settings = get_settings()
    user = message.from_user
    if user is None:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)

    webapp_url = settings.telegram_webapp_url.rstrip("/")
    name = user.first_name or "Пользователь"

    welcome_text = (
        f"👋 Здравствуйте, {hbold(name)}!\n\n"
        f"Добро пожаловать в {hbold('OmniCart AI')} — персональный ассистент покупок для "
        f"{hbold('Гулистана и Сырдарьинской области')}.\n\n"
        f"⚡️ {hbold('Что я умею делать:')}\n"
        f"• {hbold('Чек-лист прямо в чате')} — вычеркивайте товары кнопками без открытия приложений\n"
        f"• {hbold('Импорт из Xiaomi Заметок')} — отправьте скопированный список, я разберу его за секунду\n"
        f"• {hbold('Аналитика рынка Гулистана')} — сравниваю цены в {hbold('Корзинке')} (ул. Сайхун) и на {hbold('Деҳқон Бозори')}\n"
        f"• {hbold('Умный парсинг')} — напишите {hitalic('«купил 2кг мяса за 180 000 на базаре»')}, я сам всё запишу\n\n"
        f"Используйте удобное меню внизу или откройте полноэкранный Mini App:"
    )

    reply_kb = get_main_reply_keyboard(webapp_url)

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть Mini App (iOS 26)",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мой чек-лист",
                    callback_data="show_checklist",
                ),
                InlineKeyboardButton(
                    text="🏛 Корзинка vs Базар",
                    callback_data="chk_market_advise",
                ),
            ],
        ]
    )

    await message.answer(
        welcome_text,
        reply_markup=reply_kb,
        parse_mode=ParseMode.HTML,
    )

    await message.answer(
        "Быстрый доступ к чек-листу и аналитике цен:",
        reply_markup=inline_kb,
        parse_mode=ParseMode.HTML,
    )

    # Configure Telegram WebApp Menu button
    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(
                text="OmniCart",
                web_app=WebAppInfo(url=webapp_url),
            ),
        )
    except Exception as exc:
        logger.warning("Could not set chat menu button: %s", exc)


# ── Menu: Checklist (Chat view) ──────────────────────────────────────────────

@router.message(F.text.in_({"📋 Чек-лист покупок", "/list", "/checklist"}))
async def msg_checklist(message: Message, db_session: Any) -> None:
    settings = get_settings()
    session: AsyncSession = db_session
    user = message.from_user
    if not user:
        return

    db_user = await get_or_create_user(session, user)
    text, kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Menu: Xiaomi Notes Import ────────────────────────────────────────────────

@router.message(F.text.in_({"📝 Из Xiaomi Заметок", "/notes", "/import_notes"}))
async def msg_xiaomi_notes_prompt(message: Message) -> None:
    prompt = (
        f"📝 {hbold('Импорт из Xiaomi Заметок (Mi Notes)')}\n\n"
        f"Скопируйте ваш список из приложения {hbold('Заметки')} на телефоне Xiaomi и отправьте его сюда сообщением.\n\n"
        f"Поддерживаются любые форматы:\n"
        f"• Чекбоксы: {hcode('- [ ] Картошка 3кг по 4500')}\n"
        f"• Точки и списки: {hcode('• Говядина 1.5кг')}\n"
        f"• Простой текст: {hcode('молоко, масло, хлеб 2шт')}\n\n"
        f"Отправьте текст прямо сейчас, и я добавлю все позиции в ваш чек-лист!"
    )
    await message.answer(prompt, parse_mode=ParseMode.HTML)


# ── Menu: Guliston Market Advisor ────────────────────────────────────────────

@router.message(F.text.in_({"🏛 Корзинка vs Базар", "/advisor", "/bazaar", "/market"}))
async def msg_guliston_advisor(message: Message, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = message.from_user
    if not user:
        return

    db_user = await get_or_create_user(session, user)

    # Get active items from user's checklist
    result = await session.execute(
        select(PurchaseHistory.item_name)
        .where(PurchaseHistory.user_id == db_user.id, PurchaseHistory.is_purchased == False)
        .limit(20)
    )
    raw_names = result.scalars().all()
    item_names = list(raw_names) if raw_names else ["говядина", "картофель", "лук", "растительное масло", "молоко", "яйца"]

    analysis = GulistonMarketService.analyze_shopping_list(item_names)

    lines = [
        f"🏛 {hbold('Аналитика рынка: Гулистан (Сырдарья)')}\n",
        f"Сравнение: {hbold('Деҳқон Бозори')} vs {hbold('Корзинка Гулистан (ул. Сайхун)')}\n",
    ]

    bazaar = analysis["bazaar"]
    if bazaar["items"]:
        lines.append(f"🥩 {hbold('Выгоднее на Деҳқон Бозори:')}")
        for it in bazaar["items"]:
            lines.append(f"  • {hbold(it['name'])}: ~{it['bazaar_price']:,} сум ({it['unit']})")
            lines.append(f"    {hitalic(it['tip'])}")
        lines.append(f"  Подсумма на базаре: {bazaar['estimated_subtotal']:,} сум\n")

    supermarket = analysis["supermarket"]
    if supermarket["items"]:
        lines.append(f"🛒 {hbold('Выгоднее в Корзинке (ул. Сайхун):')}")
        for it in supermarket["items"]:
            lines.append(f"  • {hbold(it['name'])}: ~{it['supermarket_price']:,} сум ({it['unit']})")
            lines.append(f"    {hitalic(it['tip'])}")
        lines.append(f"  Подсумма в Корзинке: {supermarket['estimated_subtotal']:,} сум\n")

    if analysis["estimated_savings"] > 0:
        lines.append(f"💰 {hbold('Расчетная экономия:')} {analysis['estimated_savings']:,} сум")

    lines.append(f"\n💡 {analysis['summary_advice']}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍲 Калькулятор плова (Гулистан)",
                    callback_data="calc_plov_6",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Перейти к чек-листу",
                    callback_data="show_checklist",
                )
            ],
        ]
    )

    await message.answer("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Menu: Regular Staples / Replenishment ───────────────────────────────────

@router.message(F.text.in_({"💡 Регулярные товары", "/staples", "/regular"}))
async def msg_regular_staples(message: Message) -> None:
    staples = XiaomiNotesParser.generate_replenishment_checklist([])

    lines = [
        f"💡 {hbold('Регулярные товары для дома (Гулистан)')}\n",
        "Продукты, которые обычно заканчиваются каждые несколько дней:\n",
    ]

    for idx, s in enumerate(staples, 1):
        lines.append(f"{idx}. {hbold(s['item_name'])} — {s['quantity']} {s['unit']} ({s['reason']})")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить всё в чек-лист",
                    callback_data="add_all_staples",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Открыть чек-лист",
                    callback_data="show_checklist",
                )
            ],
        ]
    )

    await message.answer("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Menu: Plov Budget Calculator ─────────────────────────────────────────────

@router.message(F.text.in_({"🍲 Калькулятор плова", "/plov"}))
async def msg_plov_calculator(message: Message) -> None:
    data = GulistonMarketService.get_plov_calculator(servings=6)

    lines = [
        f"🍲 {hbold('Калькулятор плова для Гулистана')} (на 6 человек)\n",
        "Ингредиенты и расчет стоимости по ценам Деҳқон Бозори и Корзинки:\n",
    ]

    for ing in data["ingredients"]:
        lines.append(f"• {hbold(ing['name'])}: {ing['amount']} — {ing['cost']:,} сум ({ing['where']})")

    lines.append(f"\n💵 {hbold('Итого на плов:')} {data['total_uzs']:,} сум")
    lines.append(f"👤 {hbold('На 1 порцию:')} ~{data['per_person_uzs']:,} сум")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить ингредиенты плова в список",
                    callback_data="add_plov_ingredients",
                )
            ]
        ]
    )

    await message.answer("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Callback: Show Checklist ────────────────────────────────────────────────

@router.callback_query(F.data == "show_checklist")
async def cb_show_checklist(callback: CallbackQuery, db_session: Any) -> None:
    settings = get_settings()
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    text, kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


# ── Callback: Toggle Checklist Item ─────────────────────────────────────────

@router.callback_query(F.data.startswith("chk_toggle:"))
async def cb_toggle_item(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    prefix_id = callback.data.split(":", 1)[1]

    # Find item belonging to this user
    result = await session.execute(
        select(PurchaseHistory).where(PurchaseHistory.user_id == db_user.id)
    )
    items = result.scalars().all()

    target_item = None
    for it in items:
        if str(it.id).startswith(prefix_id):
            target_item = it
            break

    if target_item:
        target_item.is_purchased = not target_item.is_purchased
        await session.commit()
        status_msg = "Куплено!" if target_item.is_purchased else "Возвращено в список"
        await callback.answer(f"{target_item.item_name}: {status_msg}")
    else:
        await callback.answer("Элемент не найден")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Callback: Clear Done Items ──────────────────────────────────────────────

@router.callback_query(F.data == "chk_clear_done")
async def cb_clear_done(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    await session.execute(
        delete(PurchaseHistory).where(
            PurchaseHistory.user_id == db_user.id,
            PurchaseHistory.is_purchased == True,
        )
    )
    await session.commit()
    await callback.answer("Купленные товары удалены!")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Callback: Market Advice from Checklist ──────────────────────────────────

@router.callback_query(F.data == "chk_market_advise")
async def cb_market_advise(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    result = await session.execute(
        select(PurchaseHistory.item_name)
        .where(PurchaseHistory.user_id == db_user.id, PurchaseHistory.is_purchased == False)
        .limit(20)
    )
    raw_names = result.scalars().all()
    item_names = list(raw_names) if raw_names else ["говядина", "картофель", "лук", "растительное масло", "молоко"]

    analysis = GulistonMarketService.analyze_shopping_list(item_names)

    lines = [
        f"🏛 {hbold('Советник по рынку Гулистана:')}\n",
        f"💰 Экономия: {analysis['estimated_savings']:,} сум\n",
        f"{analysis['summary_advice']}\n",
    ]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Назад к чек-листу",
                    callback_data="show_checklist",
                )
            ]
        ]
    )

    if callback.message:
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


# ── Callback: Add Staples Quick ─────────────────────────────────────────────

@router.callback_query(F.data.in_({"add_staples_quick", "add_all_staples"}))
async def cb_add_all_staples(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    staples = XiaomiNotesParser.generate_replenishment_checklist([])
    added = 0

    for s in staples[:6]:
        p = PurchaseHistory(
            id=uuid.uuid4(),
            user_id=db_user.id,
            raw_input_text="Регулярный товар",
            item_name=s["item_name"],
            quantity=s["quantity"],
            unit=s["unit"],
            price_paid=0.0,
            currency_code="UZS",
            country_code="UZ",
            city="Гулистан",
            is_purchased=False,
        )
        session.add(p)
        added += 1

    await session.commit()
    await callback.answer(f"Добавлено {added} базовых товаров!")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Callback: Add Plov Ingredients ──────────────────────────────────────────

@router.callback_query(F.data == "add_plov_ingredients")
async def cb_add_plov(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    plov_data = GulistonMarketService.get_plov_calculator(6)

    for ing in plov_data["ingredients"]:
        p = PurchaseHistory(
            id=uuid.uuid4(),
            user_id=db_user.id,
            raw_input_text="Ингредиенты плова",
            item_name=ing["name"],
            quantity=1.0,
            unit="порц",
            price_paid=float(ing["cost"]),
            currency_code="UZS",
            country_code="UZ",
            city="Гулистан",
            is_purchased=False,
        )
        session.add(p)

    await session.commit()
    await callback.answer("Ингредиенты для плова добавлены в список!")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Intelligent Message Handler (Xiaomi Notes detection + Natural parsing) ──

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_or_notes(message: Message, db_session: Any) -> None:
    """
    Intelligently handles incoming text:
    1. Detects Xiaomi Notes format (multi-line, checkboxes, bullets).
    2. Parses natural language grocery logs or purchases.
    """
    user = message.from_user
    text = message.text
    if user is None or not text:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)

    # Check if text looks like Xiaomi Notes export (multiple lines with list markers)
    has_bullets = any(marker in text for marker in ["- [", "•", "*", "–", "\n"])
    is_multiline_list = len(text.strip().splitlines()) >= 2

    if has_bullets or is_multiline_list:
        # Parse via XiaomiNotesParser
        parsed_notes = XiaomiNotesParser.parse_note_text(text)

        if parsed_notes and len(parsed_notes) >= 2:
            added_count = 0
            for item in parsed_notes:
                purchase = PurchaseHistory(
                    id=uuid.uuid4(),
                    user_id=db_user.id,
                    raw_input_text=text[:2000],
                    item_name=item["item_name"],
                    quantity=item["quantity"],
                    unit=item["unit"],
                    price_paid=item["estimated_price"],
                    currency_code="UZS",
                    country_code="UZ",
                    city="Гулистан",
                    is_purchased=item["is_purchased"],
                )
                session.add(purchase)
                added_count += 1

            await session.commit()

            settings = get_settings()
            chk_text, chk_kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)

            success_msg = (
                f"✅ {hbold('Импортировано из Заметок Xiaomi:')} {added_count} позиций!\n\n"
                f"Список сохранен в ваш чек-лист:"
            )
            await message.answer(success_msg, parse_mode=ParseMode.HTML)
            await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)
            return

    # Single-line purchase or query parsing via B.AI
    processing_msg = await message.answer("✨ Обрабатываю запись...")

    try:
        async with BAIClient() as client:
            parsed = await client.parse_purchase_text(
                text[:2000],
                country="UZ",
                city="Гулистан",
                currency="UZS",
                measurement="metric",
                shopping_culture="mixed",
            )
    except BAIClientError as exc:
        logger.error("B.AI parse failed: %s", exc)
        await processing_msg.edit_text("❌ Не удалось распознать запись. Попробуйте еще раз.")
        return

    if not parsed.items:
        # Fallback: simple item addition
        cleaned_item = re.sub(r"[^\w\sа-яА-ЯёЁўқғҳЎҚҒҲ0-9]", "", text).strip()[:100]
        if cleaned_item:
            purchase = PurchaseHistory(
                id=uuid.uuid4(),
                user_id=db_user.id,
                raw_input_text=text,
                item_name=cleaned_item.capitalize(),
                quantity=1.0,
                unit="шт",
                price_paid=0.0,
                currency_code="UZS",
                country_code="UZ",
                city="Гулистан",
                is_purchased=False,
            )
            session.add(purchase)
            await session.commit()

            settings = get_settings()
            chk_text, chk_kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)
            await processing_msg.edit_text(
                f"✅ Добавлено в список: {hbold(cleaned_item.capitalize())}",
                parse_mode=ParseMode.HTML,
            )
            await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)
        else:
            await processing_msg.edit_text(
                "🤔 Не удалось найти товары. Отправьте список продуктов или сумму."
            )
        return

    # Save recognized items
    saved_count = 0
    for pi in parsed.items:
        clean_name = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", pi.item_name)[:255]
        purchase = PurchaseHistory(
            id=uuid.uuid4(),
            user_id=db_user.id,
            raw_input_text=text[:2000],
            item_name=clean_name.capitalize(),
            quantity=pi.quantity,
            unit=pi.unit,
            price_paid=pi.price,
            currency_code="UZS",
            store_name=pi.store_name[:255] if pi.store_name else None,
            country_code="UZ",
            city="Гулистан",
            is_purchased=False,
            ai_parsed_data=pi.model_dump(mode="json"),
        )
        session.add(purchase)
        saved_count += 1

    await session.commit()

    lines = [f"✅ Добавлено позиций: {hbold(str(saved_count))}\n"]
    for pi in parsed.items:
        qty = pi.quantity
        qty_str = f"{qty:.0f}" if qty == int(qty) else f"{qty:.1f}"
        price_str = f"{pi.price:,.0f}" if pi.price > 0 else "цена не указана"
        store = f" ({pi.store_name})" if pi.store_name else ""
        lines.append(f"  • {hbold(pi.item_name)}: {qty_str} {pi.unit} — {price_str} сум{store}")

    settings = get_settings()
    chk_text, chk_kb = await render_checklist_message(session, db_user.id, settings.telegram_webapp_url)

    await processing_msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)
    await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)
