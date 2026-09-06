"""
OmniCart AI — Streamlined Telegram Bot Handlers (Phases 1-5).
Features:
- Minimalist 3-button bottom keyboard: [📋 Мой список, 🛒 Добавить регулярные, 🚀 Открыть приложение]
- Vibrant, grouped emoji formatting for high readability on the bazaar floor (🥩, 🥦, 🍞, 🥛, 🧼)
- Universal AI parser for any text / copied Xiaomi notes
- Voice message handler (Whisper Voice-to-JSON)
- Recipe analysis & ingredient scaling
- Family Cart synchronization via deep-links (/start cart_<id>)
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from decimal import Decimal
from typing import Any, Optional

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.markdown import hbold, hcode, hitalic
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from database.models import PurchaseHistory, User, UserSettings, hash_telegram_id
from services.b_ai_client import BAIClient
from services.cron_parser import PriceCronService
from services.universal_ai_parser import UniversalAIParser

logger = logging.getLogger(__name__)

router = Router(name="start")


# ── Clean 3-Button Bottom Keyboard (Phase 1) ────────────────────────────────

def get_main_reply_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """Streamlined persistent keyboard with only 3 essential actions."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Мой список"),
                KeyboardButton(text="🛒 Добавить регулярные"),
            ],
            [
                KeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=webapp_url)),
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
            family_cart_id=None,
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


def get_effective_cart_id(user: User) -> uuid.UUID:
    """Returns user's own ID or their shared family cart ID."""
    return user.family_cart_id if user.family_cart_id else user.id


# ── Helper: Render In-Chat Checklist with Emojis & Market Aisles ────────────

async def render_checklist_message(
    session: AsyncSession, db_user: User, webapp_url: str
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Renders shopping list grouped by bazaar aisles with clear emojis for instant
    glance reading while walking in the market.
    """
    cart_id = get_effective_cart_id(db_user)
    is_family = bool(db_user.family_cart_id)

    result = await session.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.user_id == cart_id)
        .order_by(PurchaseHistory.is_purchased.asc(), PurchaseHistory.category.asc(), PurchaseHistory.created_at.desc())
        .limit(25)
    )
    items = result.scalars().all()

    if not items:
        family_tag = f" 👥 {hitalic('(Семейная корзина)')}" if is_family else ""
        text = (
            f"📋 {hbold('Ваш список покупок пуст')}{family_tag}\n\n"
            f"⚡️ {hbold('Как добавить товары:')}\n"
            f"• 🎙 Надиктуйте голосовое: {hitalic('«Купи 2 кг говядины и 3 лепешки»')}\n"
            f"• 📝 Отправьте любой текст или скопируйте из {hbold('Заметок')}\n"
            f"• 🍲 Скиньте рецепт для расчета ингредиентов\n"
            f"• Или нажмите кнопку {hbold('«🛒 Добавить регулярные»')} ниже"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 Добавить регулярные товары",
                        callback_data="add_staples_quick",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔗 Поделиться с семьей",
                        callback_data="share_family_cart",
                    ),
                    InlineKeyboardButton(
                        text="🚀 В приложение",
                        web_app=WebAppInfo(url=webapp_url),
                    ),
                ],
            ]
        )
        return text, kb

    pending_items = [i for i in items if not i.is_purchased]
    purchased_items = [i for i in items if i.is_purchased]

    total_est = sum(float(i.price_paid or 0) for i in pending_items)
    family_header = " 👥 Семейная корзина" if is_family else " 📍 Базар Гулистан"

    lines = [
        f"📋 {hbold('Список покупок')}{family_header}",
        f"Осталось купить: {hbold(str(len(pending_items)))} | В корзине: {len(purchased_items)}",
    ]
    if total_est > 0:
        lines.append(f"💰 Сумма: {hbold(f'{total_est:,.0f}')} сум\n")
    else:
        lines.append("")

    # Group pending items by bazaar aisles
    grouped: dict[str, list[PurchaseHistory]] = {}
    for it in pending_items:
        cat = it.category or "🥫 Бакалея и специи"
        grouped.setdefault(cat, []).append(it)

    inline_rows: list[list[InlineKeyboardButton]] = []

    # Display pending items grouped by aisle
    item_num = 1
    for cat_name, cat_items in grouped.items():
        lines.append(hbold(cat_name))
        for it in cat_items:
            qty_str = f"{it.quantity:.0f}" if it.quantity == int(it.quantity) else f"{it.quantity:.1f}"
            price_str = f" (~{it.price_paid:,.0f} сум)" if it.price_paid and it.price_paid > 0 else ""
            lines.append(f"  {item_num}. [ ] {it.item_name} — {qty_str} {it.unit}{price_str}")

            # Inline toggle button
            btn_title = f"✓ {it.item_name[:15]}"
            inline_rows.append([
                InlineKeyboardButton(
                    text=btn_title,
                    callback_data=f"chk_toggle:{str(it.id)[:8]}",
                )
            ])
            item_num += 1
        lines.append("")

    # Display already purchased items at bottom
    if purchased_items:
        lines.append(hbold("✅ Уже куплено:"))
        for pit in purchased_items[:6]:
            lines.append(f"  <s>[x] {pit.item_name}</s>")

    # Action row
    action_row = [
        InlineKeyboardButton(text="🔗 Поделиться", callback_data="share_family_cart"),
        InlineKeyboardButton(text="🗑 Очистить купленное", callback_data="chk_clear_done"),
    ]
    inline_rows.append(action_row)
    inline_rows.append([
        InlineKeyboardButton(
            text="🚀 Открыть приложение (iOS 26)",
            web_app=WebAppInfo(url=webapp_url),
        )
    ])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=inline_rows)


# ── /start Handler (with Deep-Link Family Cart support) ──────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db_session: Any, bot: Bot) -> None:
    """Welcome handler supporting direct /start and deep-linked /start cart_<uuid>."""
    settings = get_settings()
    user = message.from_user
    if user is None:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    webapp_url = settings.telegram_webapp_url.rstrip("/")

    # Check deep-link argument (e.g. cart_a1b2c3d4-...)
    if command.args and command.args.startswith("cart_"):
        target_cart_id_str = command.args.replace("cart_", "").strip()
        try:
            target_uuid = uuid.UUID(target_cart_id_str)
            db_user.family_cart_id = target_uuid
            await session.commit()
            await message.answer(
                f"🎉 {hbold('Вы подключились к семейной корзине!')}\n\n"
                f"Теперь ваши списки покупок синхронизированы. Все добавления и вычеркивания "
                f"отображаются у всех участников в реальном времени.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.warning("Invalid family cart deep-link: %s", exc)

    welcome_text = (
        f"👋 Здравствуйте, {hbold(user.first_name or 'Пользователь')}!\n\n"
        f"Я — ваш умный ассистент покупок {hbold('OmniCart AI')} для рынка и магазинов "
        f"{hbold('Гулистана')}.\n\n"
        f"⚡️ {hbold('Быстрые возможности:')}\n"
        f"• 🎙 {hbold('Голосовой ввод')} — надиктуйте товары голосом\n"
        f"• 📝 {hbold('Любой текст')} — скопируйте список из Заметок, я сам всё разберу\n"
        f"• 🍲 {hbold('Рецепты')} — пришлите рецепт, я вытащу граммовки на нужное число персон\n"
        f"• 👥 {hbold('Семейная корзина')} — ходите на базар вместе с одного списка"
    )

    reply_kb = get_main_reply_keyboard(webapp_url)
    chk_text, chk_kb = await render_checklist_message(session, db_user, webapp_url)

    await message.answer(welcome_text, reply_markup=reply_kb, parse_mode=ParseMode.HTML)
    await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)


# ── Quick Bottom Menu Actions ────────────────────────────────────────────────

@router.message(F.text.in_({"📋 Мой список", "📋 Чек-лист покупок"}))
async def msg_show_checklist(message: Message, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = message.from_user
    if not user:
        return
    db_user = await get_or_create_user(session, user)
    settings = get_settings()

    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.message(F.text.in_({"🛒 Добавить регулярные", "💡 Регулярные товары"}))
async def msg_add_staples(message: Message, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = message.from_user
    if not user:
        return
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    staples = [
        {"name": "Говядина мякоть", "qty": 1.5, "unit": "кг", "category": "🥩 Мясной отдел", "price": 135000},
        {"name": "Картофель красный", "qty": 4.0, "unit": "кг", "category": "🥦 Овощные ряды", "price": 16000},
        {"name": "Лук репчатый", "qty": 2.0, "unit": "кг", "category": "🥦 Овощные ряды", "price": 6000},
        {"name": "Масло хлопковое 2л", "qty": 1.0, "unit": "бут", "category": "🥫 Бакалея и специи", "price": 37000},
        {"name": "Лепешки тандырные", "qty": 3.0, "unit": "шт", "category": "🍞 Лепешки и выпечка", "price": 12000},
    ]

    added = 0
    for s in staples:
        p = PurchaseHistory(
            id=uuid.uuid4(),
            user_id=cart_id,
            raw_input_text="Регулярный базовый товар",
            item_name=s["name"],
            category=s["category"],
            quantity=Decimal(str(s["qty"])),
            unit=s["unit"],
            price_paid=Decimal(str(s["price"])),
            currency_code="UZS",
            country_code="UZ",
            city="Гулистан",
            is_purchased=False,
        )
        session.add(p)
        added += 1

    await session.commit()
    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)

    await message.answer(f"✅ Добавлено {hbold(str(added))} регулярных товаров для дома!", parse_mode=ParseMode.HTML)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Voice Message Handler (Whisper Voice-to-JSON) ────────────────────────────

@router.message(F.voice | F.audio)
async def handle_voice_message(message: Message, db_session: Any, bot: Bot) -> None:
    """Transcribes voice notes using Whisper and parses items through Universal AI Parser."""
    user = message.from_user
    if not user:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    status_msg = await message.answer("🎙 Слушаю и распознаю голосовое...")

    try:
        # Download voice file
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_bytes)
        audio_data = file_bytes.getvalue()

        # Transcribe via Whisper
        async with BAIClient() as client:
            transcription = await client.transcribe_audio(audio_data, filename="voice.ogg")

        if not transcription:
            await status_msg.edit_text("❌ Не удалось разобрать аудио. Попробуйте наговорить четче или напишите текстом.")
            return

        await status_msg.edit_text(f"🗣 {hitalic(f'«{transcription}»')}\n✨ Добавляю в список...")

        # Parse through Universal AI Parser
        parse_result = await UniversalAIParser.parse_any_text(transcription)

        if not parse_result.items:
            await status_msg.edit_text(f"🤔 Распознано: «{transcription}», но товары не найдены. Назовите продукты.")
            return

        for it in parse_result.items:
            p = PurchaseHistory(
                id=uuid.uuid4(),
                user_id=cart_id,
                raw_input_text=transcription,
                item_name=it.name,
                category=it.category,
                quantity=Decimal(str(it.qty)),
                unit=it.unit,
                price_paid=Decimal(str(it.estimated_price)),
                currency_code="UZS",
                country_code="UZ",
                city="Гулистан",
                is_purchased=False,
            )
            session.add(p)

        await session.commit()
        settings = get_settings()
        text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)

        await status_msg.edit_text(f"✅ Добавлено из голоса: {hbold(str(len(parse_result.items)))} поз.", parse_mode=ParseMode.HTML)
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.exception("Voice handling error: %s", exc)
        await status_msg.edit_text("❌ Ошибка при обработке аудио. Попробуйте отправить текстом.")


# ── Text & Recipe Handler (Universal Parser) ────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_or_recipe(message: Message, db_session: Any) -> None:
    """Universal handler for free text, copied notes, and recipe links/texts."""
    user = message.from_user
    text = message.text
    if not user or not text:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    # Check if text is a recipe or link
    is_recipe = any(w in text.lower() for w in ["рецепт", "ингредиент", "порци", "приготовлени", "youtube.com", "youtu.be", "плов", "шурпа", "лагман", "манты"])

    status_msg = await message.answer("✨ Разбираю запись нейросетью...")

    try:
        if is_recipe:
            parse_result = await UniversalAIParser.parse_recipe(text, servings=4)
        else:
            parse_result = await UniversalAIParser.parse_any_text(text)

        if not parse_result.items:
            await status_msg.edit_text("🤔 Не удалось распознать товары. Напишите продукты, например: «картошка 2кг, мясо 1кг».")
            return

        added_count = 0
        for it in parse_result.items:
            p = PurchaseHistory(
                id=uuid.uuid4(),
                user_id=cart_id,
                raw_input_text=text[:2000],
                item_name=it.name,
                category=it.category,
                quantity=Decimal(str(it.qty)),
                unit=it.unit,
                price_paid=Decimal(str(it.estimated_price)),
                currency_code="UZS",
                country_code="UZ",
                city="Гулистан",
                is_purchased=False,
            )
            session.add(p)
            added_count += 1

        await session.commit()
        settings = get_settings()
        chk_text, chk_kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)

        tag = "по рецепту" if is_recipe else "в список"
        await status_msg.edit_text(f"✅ Добавлено {tag}: {hbold(str(added_count))} позиций!", parse_mode=ParseMode.HTML)
        await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.exception("Text parse error: %s", exc)
        await status_msg.edit_text("❌ Ошибка разбора. Попробуйте еще раз.")


# ── Inline Callbacks (Toggles, Clear, Family Share) ──────────────────────────

@router.callback_query(F.data.startswith("chk_toggle:"))
async def cb_toggle_item(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    prefix_id = callback.data.split(":", 1)[1]

    result = await session.execute(
        select(PurchaseHistory).where(PurchaseHistory.user_id == cart_id)
    )
    items = result.scalars().all()

    target = next((it for it in items if str(it.id).startswith(prefix_id)), None)
    if target:
        target.is_purchased = not target.is_purchased
        await session.commit()
        status_word = "куплено!" if target.is_purchased else "возвращено"
        await callback.answer(f"{target.item_name}: {status_word}")
    else:
        await callback.answer("Товар не найден")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "chk_clear_done")
async def cb_clear_done(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    await session.execute(
        delete(PurchaseHistory).where(
            PurchaseHistory.user_id == cart_id,
            PurchaseHistory.is_purchased == True,
        )
    )
    await session.commit()
    await callback.answer("Купленные товары удалены!")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "share_family_cart")
async def cb_share_family(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    # Share link is based on user's ID
    share_link = f"https://t.me/gusop_bot?start=cart_{str(db_user.id)}"

    msg = (
        f"🔗 {hbold('Ссылка на вашу семейную корзину:')}\n\n"
        f"{hcode(share_link)}\n\n"
        f"Отправьте эту ссылку супругу(е) или родственникам. При переходе их список "
        f"автоматически объединится с вашим в реальном времени!"
    )
    await callback.answer()
    if callback.message:
        await callback.message.answer(msg, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "add_staples_quick")
async def cb_add_staples_quick(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    staples = [
        ("Говядина мякоть", 1.5, "кг", "🥩 Мясной отдел", 135000),
        ("Картофель красный", 3.0, "кг", "🥦 Овощные ряды", 12000),
        ("Лук репчатый", 2.0, "кг", "🥦 Овощные ряды", 6000),
        ("Масло хлопковое", 1.0, "л", "🥫 Бакалея и специи", 18500),
        ("Лепешки тандырные", 2.0, "шт", "🍞 Лепешки и выпечка", 8000),
    ]

    for name, qty, unit, cat, price in staples:
        p = PurchaseHistory(
            id=uuid.uuid4(),
            user_id=cart_id,
            raw_input_text="Быстрые регулярные",
            item_name=name,
            category=cat,
            quantity=Decimal(str(qty)),
            unit=unit,
            price_paid=Decimal(str(price)),
            currency_code="UZS",
            country_code="UZ",
            city="Гулистан",
            is_purchased=False,
        )
        session.add(p)

    await session.commit()
    await callback.answer("Базовые товары добавлены!")

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
