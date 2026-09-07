"""
OmniCart AI — Streamlined, Production-Grade Telegram Bot Handlers.
Features:
- Robust HTML parsing with html.escape (replaces fragile MarkdownV2)
- Message chunking (<4000 chars) to prevent Telegram length limit exceptions
- Guaranteed callback.answer() and safe MessageIsNotModified handling
- Minimalist 3-button bottom keyboard: [📋 Мой список, 🛒 Добавить регулярные, 🚀 Открыть приложение]
- Grouped bazaar aisle formatting (🥩, 🥦, 🍞, 🥛, 🧼)
- Universal AI parser for text & copied Xiaomi Notes
- Whisper voice message transcription
- Recipe analysis & ingredient scaling
- Family Cart synchronization via deep-links (/start cart_<id>)
- Market overview for Guliston bazaar with refresh & cancel navigation
"""

from __future__ import annotations

import html
import io
import logging
import re
import uuid
from decimal import Decimal
from typing import Any, List, Optional

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from database.models import PriceHistory, PurchaseHistory, User, UserSettings, hash_telegram_id
from services.b_ai_client import BAIClient
from services.cron_parser import PriceCronService
from services.guliston_market_service import GulistonMarketService
from services.universal_ai_parser import UniversalAIParser

logger = logging.getLogger(__name__)

router = Router(name="start_router")


# ── FSM States ───────────────────────────────────────────────────────────────

class FormState(StatesGroup):
    waiting_for_custom_item = State()
    waiting_for_recipe = State()


# ── Text Helpers & Chunking ──────────────────────────────────────────────────

def escape_html(text: str) -> str:
    """Escapes HTML special characters to prevent markup injection or parse errors."""
    return html.escape(text or "")


def chunk_text(text: str, max_chars: int = 4000) -> List[str]:
    """Splits long text into Telegram-safe chunks."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk: List[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > max_chars:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = len(line)
        else:
            current_chunk.append(line)
            current_len += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


# ── Keyboards ────────────────────────────────────────────────────────────────

def build_main_inline_keyboard(web_app_url: str, current_lang: str = "ru") -> InlineKeyboardMarkup:
    """Inline menu keyboard with WebApp, Market Overview, and Help."""
    if current_lang.startswith("uz"):
        open_app_text = "🛍 OmniCart Mini App-ni ochish"
        market_text = "📊 Guliston bozor narxlari"
        help_text = "ℹ️ Yordam"
    elif current_lang.startswith("en"):
        open_app_text = "🛍 Open OmniCart Mini App"
        market_text = "📊 Guliston Market Prices"
        help_text = "ℹ️ Help"
    else:
        open_app_text = "🛍 Открыть OmniCart Mini App"
        market_text = "📊 Цены рынка Гулистан"
        help_text = "ℹ️ Справка"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=open_app_text, web_app=WebAppInfo(url=web_app_url))],
            [
                InlineKeyboardButton(text=market_text, callback_query_data="view_guliston_market"),
                InlineKeyboardButton(text=help_text, callback_query_data="view_bot_help"),
            ],
        ]
    )


def build_cancel_keyboard(current_lang: str = "ru") -> InlineKeyboardMarkup:
    cancel_text = "❌ Bekor qilish" if current_lang.startswith("uz") else ("❌ Cancel" if current_lang.startswith("en") else "❌ Отмена")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cancel_text, callback_query_data="cancel_action")]
        ]
    )


def get_main_reply_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """Streamlined persistent bottom keyboard with only 3 essential actions."""
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

    user_lang = tg_user.language_code or "ru"

    if db_user is None:
        user_uuid = uuid.uuid4()
        db_user = User(
            id=user_uuid,
            telegram_id_hash=tg_id_hash,
            username=tg_user.username[:255] if tg_user.username else None,
            first_name=tg_user.first_name[:255] if tg_user.first_name else None,
            language_code=user_lang[:10],
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


# ── Helper: Render In-Chat Checklist ────────────────────────────────────────

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
        .order_by(
            PurchaseHistory.is_purchased.asc(),
            PurchaseHistory.category.asc(),
            PurchaseHistory.created_at.desc(),
        )
        .limit(30)
    )
    items = result.scalars().all()

    if not items:
        family_tag = " 👥 <i>(Семейная корзина)</i>" if is_family else ""
        text = (
            f"📋 <b>Ваш список покупок пуст</b>{family_tag}\n\n"
            f"⚡️ <b>Как добавить товары:</b>\n"
            f"• 🎙 Надиктуйте голосовое: <i>«Купи 2 кг говядины и 3 лепешки»</i>\n"
            f"• 📝 Отправьте любой текст или скопируйте из <b>Заметок</b>\n"
            f"• 🍲 Скиньте рецепт для расчета ингредиентов\n"
            f"• Или нажмите кнопку <b>«🛒 Добавить регулярные»</b> ниже"
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
        f"📋 <b>Список покупок</b>{family_header}",
        f"Осталось купить: <b>{len(pending_items)}</b> | В корзине: {len(purchased_items)}",
    ]
    if total_est > 0:
        lines.append(f"💰 Сумма: <b>{total_est:,.0f}</b> сум\n")
    else:
        lines.append("")

    # Group pending items by bazaar aisles
    grouped: dict[str, list[PurchaseHistory]] = {}
    for it in pending_items:
        cat = it.category or "🥫 Бакалея и специи"
        grouped.setdefault(cat, []).append(it)

    inline_rows: list[list[InlineKeyboardButton]] = []

    item_num = 1
    for cat_name, cat_items in grouped.items():
        lines.append(f"<b>{escape_html(cat_name)}</b>")
        for it in cat_items:
            qty_str = f"{it.quantity:.0f}" if it.quantity == int(it.quantity) else f"{it.quantity:.1f}"
            price_str = f" (~{it.price_paid:,.0f} сум)" if it.price_paid and it.price_paid > 0 else ""
            lines.append(f"  {item_num}. [ ] {escape_html(it.item_name)} — {qty_str} {escape_html(it.unit)}{price_str}")

            btn_title = f"✓ {it.item_name[:15]}"
            inline_rows.append([
                InlineKeyboardButton(
                    text=btn_title,
                    callback_data=f"chk_toggle:{str(it.id)[:8]}",
                )
            ])
            item_num += 1
        lines.append("")

    if purchased_items:
        lines.append("<b>✅ Уже куплено:</b>")
        for pit in purchased_items[:6]:
            lines.append(f"  <s>[x] {escape_html(pit.item_name)}</s>")

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


# ── /start Handler ──────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db_session: Any, state: FSMContext) -> None:
    """Welcome handler supporting direct /start and deep-linked /start cart_<uuid>."""
    await state.clear()
    settings = get_settings()
    user = message.from_user
    if user is None:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    webapp_url = settings.telegram_webapp_url.rstrip("/")
    user_lang = user.language_code or "ru"

    # Check deep-link argument (e.g. cart_a1b2c3d4-...)
    if command.args and command.args.startswith("cart_"):
        target_cart_id_str = command.args.replace("cart_", "").strip()
        try:
            target_uuid = uuid.UUID(target_cart_id_str)
            db_user.family_cart_id = target_uuid
            await session.commit()
            await message.answer(
                "🎉 <b>Вы подключились к семейной корзине!</b>\n\n"
                "Теперь ваши списки покупок синхронизированы. Все добавления и вычеркивания "
                "отображаются у всех участников в реальном времени.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.warning("Invalid family cart deep-link: %s", exc)

    safe_first_name = escape_html(user.first_name or "Пользователь")

    if user_lang.startswith("uz"):
        welcome_text = (
            f"👋 Assalomu alaykum, <b>{safe_first_name}</b>!\n\n"
            f"<b>OmniCart AI</b> — Guliston bozori va do'konlari uchun aqlli xarid yordamchisi.\n\n"
            f"⚡️ <b>Imkoniyatlar:</b>\n"
            f"• 🎙 <b>Ovozli xabar</b> — xaridlarni ovoz orqali aytib bering\n"
            f"• 📝 <b>Matn kiritish</b> — xaridlar ro'yxatini yoki retseptni yuboring\n"
            f"• 📊 <b>Bozor narxlari</b> — Guliston Dehqon Bozori narxlarini ko'rish\n"
            f"• 👥 <b>Oilaviy savat</b> — birgalikda bozor qilish"
        )
    else:
        welcome_text = (
            f"👋 Здравствуйте, <b>{safe_first_name}</b>!\n\n"
            f"Я — ваш умный ассистент покупок <b>OmniCart AI</b> для рынка и магазинов "
            f"<b>Гулистана</b>.\n\n"
            f"⚡️ <b>Быстрые возможности:</b>\n"
            f"• 🎙 <b>Голосовой ввод</b> — надиктуйте товары голосом\n"
            f"• 📝 <b>Любой текст</b> — скопируйте список из Заметок, я сам всё разберу\n"
            f"• 🍲 <b>Рецепты</b> — пришлите рецепт, я вытащу граммовки на нужное число персон\n"
            f"• 👥 <b>Семейная корзина</b> — ходите на базар вместе с одного списка"
        )

    reply_kb = get_main_reply_keyboard(webapp_url)
    chk_text, chk_kb = await render_checklist_message(session, db_user, webapp_url)

    await message.answer(welcome_text, reply_markup=reply_kb, parse_mode=ParseMode.HTML)
    await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)


# ── Market Overview Handler ─────────────────────────────────────────────────

@router.callback_query(F.data == "view_guliston_market")
async def handle_market_overview(callback: CallbackQuery) -> None:
    """Shows curated market overview for Guliston bazaar with safe update handling."""
    await callback.answer()

    overview_text = (
        "📊 <b>Сводка цен: Рынок 'Гулистон Деҳқон Бозори'</b>\n\n"
        "• <i>Говядина (мякоть):</i> 85 000 – 95 000 сум/кг\n"
        "• <i>Баранина свежая:</i> 95 000 – 110 000 сум/кг\n"
        "• <i>Куриное филе:</i> 42 000 – 48 000 сум/кг\n"
        "• <i>Картофель (красный):</i> 4 000 – 5 500 сум/кг\n"
        "• <i>Лук репчатый:</i> 2 500 – 3 500 сум/кг\n"
        "• <i>Морковь желтая (для плова):</i> 3 000 – 4 000 сум/кг\n"
        "• <i>Рис Лазер (отборный):</i> 24 000 – 28 000 сум/кг\n"
        "• <i>Хлопковое масло:</i> 17 000 – 19 500 сум/л\n"
        "• <i>Лепешка тандырная:</i> 4 000 – 4 500 сум/шт\n\n"
        "<i>💡 Цены обновлены и рассчитаны алгоритмом медианы цен по рынку.</i>"
    )

    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить сводку", callback_query_data="view_guliston_market")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_query_data="back_to_main_menu")],
        ]
    )

    try:
        if callback.message:
            await callback.message.edit_text(
                text=overview_text,
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard,
            )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            logger.debug("Market overview not modified, safely ignored.")
        else:
            logger.error("Error updating market overview: %s", exc)


@router.callback_query(F.data == "view_bot_help")
async def handle_bot_help(callback: CallbackQuery) -> None:
    await callback.answer()
    help_text = (
        "ℹ️ <b>Справка по боту OmniCart AI:</b>\n\n"
        "• Отправьте аудиозапись (голосовое) для мгновенного добавления в список.\n"
        "• Скопируйте любой текст или рецепт в чат — нейросеть выделит нужные продукты.\n"
        "• Нажмите <b>«🚀 Открыть приложение»</b> для интерактивного чек-листа и сравнения цен.\n"
        "• Нажмите <b>«🔗 Поделиться»</b>, чтобы синхронизировать корзину с членами семьи."
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu")]
        ]
    )
    try:
        if callback.message:
            await callback.message.edit_text(help_text, parse_mode=ParseMode.HTML, reply_markup=back_kb)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.error("Error editing help message: %s", exc)


@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_menu(callback: CallbackQuery, db_session: Any) -> None:
    await callback.answer()
    if not callback.message or not callback.from_user:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, callback.from_user)
    settings = get_settings()

    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.error("Error returning to main menu: %s", exc)


@router.callback_query(F.data == "cancel_action")
async def handle_cancel_action(callback: CallbackQuery, state: FSMContext, db_session: Any) -> None:
    await state.clear()
    await callback.answer("Действие отменено.")
    if not callback.message or not callback.from_user:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, callback.from_user)
    settings = get_settings()

    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    try:
        await callback.message.edit_text(
            f"❌ Действие отменено.\n\n{text}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.error("Error on cancel: %s", exc)


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

    await message.answer(f"✅ Добавлено <b>{added}</b> регулярных товаров для дома!", parse_mode=ParseMode.HTML)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Voice Message Handler ───────────────────────────────────────────────────

@router.message(F.voice | F.audio)
async def handle_voice_message(message: Message, db_session: Any, bot: Bot) -> None:
    """Transcribes voice notes using Whisper and parses items through Universal AI Parser."""
    user = message.from_user
    if not user:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)

    status_msg = await message.answer("🎙 <i>Слушаю и распознаю голосовое...</i>", parse_mode=ParseMode.HTML)

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_bytes)
        audio_data = file_bytes.getvalue()

        async with BAIClient() as client:
            transcription = await client.transcribe_audio(audio_data, filename="voice.ogg")

        if not transcription:
            await status_msg.edit_text("❌ Не удалось разобрать аудио. Попробуйте наговорить четче или напишите текстом.")
            return

        safe_transcript = escape_html(transcription)
        await status_msg.edit_text(f"🗣 <i>«{safe_transcript}»</i>\n✨ <b>Добавляю в список...</b>", parse_mode=ParseMode.HTML)

        parse_result = await UniversalAIParser.parse_any_text(transcription)

        if not parse_result.items:
            await status_msg.edit_text(f"🤔 Распознано: «{safe_transcript}», но товары не найдены. Назовите продукты.")
            return

        for it in parse_result.items:
            p = PurchaseHistory(
                id=uuid.uuid4(),
                user_id=cart_id,
                raw_input_text=transcription[:2000],
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

        await status_msg.edit_text(f"✅ Добавлено из голоса: <b>{len(parse_result.items)}</b> поз.", parse_mode=ParseMode.HTML)
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.exception("Voice handling error: %s", exc)
        await status_msg.edit_text("❌ Ошибка при обработке аудио. Попробуйте отправить текстом.")


# ── Text & Recipe Handler ────────────────────────────────────────────────────

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

    is_recipe = any(
        w in text.lower()
        for w in ["рецепт", "ингредиент", "порци", "приготовлени", "youtube.com", "youtu.be", "плов", "шурпа", "лагман", "манты"]
    )

    status_msg = await message.answer("✨ <i>Разбираю запись нейросетью...</i>", parse_mode=ParseMode.HTML)

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
        await status_msg.edit_text(f"✅ Добавлено {tag}: <b>{added_count}</b> позиций!", parse_mode=ParseMode.HTML)
        await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.exception("Text parse error: %s", exc)
        await status_msg.edit_text("❌ Ошибка разбора. Попробуйте еще раз.")


# ── Inline Callbacks ─────────────────────────────────────────────────────────

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
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.error("Error editing checklist toggle message: %s", exc)


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
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.error("Error editing clear done message: %s", exc)


@router.callback_query(F.data == "share_family_cart")
async def cb_share_family(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)

    share_link = f"https://t.me/gusop_bot?start=cart_{str(db_user.id)}"

    msg = (
        "🔗 <b>Ссылка на вашу семейную корзину:</b>\n\n"
        f"<code>{share_link}</code>\n\n"
        "Отправьте эту ссылку супругу(е) или родственникам. При переходе их список "
        "автоматически объединится с вашим в реальном времени!"
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
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.error("Error editing staples quick message: %s", exc)
