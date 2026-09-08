"""
OmniCart AI — Telegram Bot Handlers.
Fast, reliable in-chat checklist management with voice/text input and family sync.
"""

from __future__ import annotations

import html
import io
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, List, Optional

from aiogram import Bot, F, Router, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandObject, CommandStart
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

from bot.i18n import STRINGS as BOT_STRINGS, t
from core.config import get_settings
from core.security import decrypt_telegram_id, encrypt_telegram_id
from database.models import PurchaseHistory, User, UserSettings, hash_telegram_id
from services.b_ai_client import BAIClient
from services.universal_ai_parser import UniversalAIParser

logger = logging.getLogger(__name__)

router = Router(name="start_router")


class FormState(StatesGroup):
    waiting_for_custom_item = State()
    waiting_for_recipe = State()


# ── Rate Limiter for Deep-Link Joins ──────────────────────────────────────────
_JOIN_ATTEMPTS: dict[int, list[float]] = {}


def _check_join_rate_limit(user_id: int) -> bool:
    now = time.time()
    cutoff = now - 3600
    attempts = [ts for ts in _JOIN_ATTEMPTS.get(user_id, []) if ts > cutoff]
    if len(attempts) >= 3:
        return False
    attempts.append(now)
    _JOIN_ATTEMPTS[user_id] = attempts
    return True


def escape_html(text: str) -> str:
    return html.escape(text or "")


def chunk_text(text: str, max_chars: int = 4000) -> List[str]:
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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("open_app", current_lang), web_app=WebAppInfo(url=web_app_url))],
            [InlineKeyboardButton(text=t("help", current_lang), callback_data="view_bot_help")],
        ]
    )


def build_cancel_keyboard(current_lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("cancel", current_lang), callback_data="cancel_action")]
        ]
    )


def get_main_reply_keyboard(webapp_url: str, current_lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("my_list", current_lang)),
                KeyboardButton(text=t("add_staples", current_lang)),
            ],
            [
                KeyboardButton(text=t("open_webapp", current_lang), web_app=WebAppInfo(url=webapp_url)),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ── User DB Helper ──────────────────────────────────────────────────────────

async def get_or_create_user(session: AsyncSession, tg_user: types.User) -> User:
    settings = get_settings()
    tg_id_hash = hash_telegram_id(tg_user.id)
    encrypted_tg_id = encrypt_telegram_id(tg_user.id, settings.secret_key) if settings.secret_key else None

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
            telegram_id_encrypted=encrypted_tg_id,
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
            city="Ташкент",
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
        if encrypted_tg_id and db_user.telegram_id_encrypted != encrypted_tg_id:
            db_user.telegram_id_encrypted = encrypted_tg_id
            changed = True
        if changed:
            await session.commit()

    return db_user


def get_effective_cart_id(user: User) -> uuid.UUID:
    return user.family_cart_id if user.family_cart_id else user.id


# ── Checklist Renderer ──────────────────────────────────────────────────────

async def render_checklist_message(
    session: AsyncSession, db_user: User, webapp_url: str
) -> tuple[str, InlineKeyboardMarkup]:
    cart_id = get_effective_cart_id(db_user)
    is_family = bool(db_user.family_cart_id)
    lang = db_user.language_code or "ru"

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
        family_tag = t("family_cart_badge", lang) if is_family else ""
        text = t("empty_list", lang) + family_tag
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("add_staples", lang),
                        callback_data="add_staples_quick",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=t("share", lang),
                        callback_data="share_family_cart",
                    ),
                    InlineKeyboardButton(
                        text=t("open_webapp", lang),
                        web_app=WebAppInfo(url=webapp_url),
                    ),
                ],
            ]
        )
        return text, kb

    pending_items = [i for i in items if not i.is_purchased]
    purchased_items = [i for i in items if i.is_purchased]

    total_est = sum(float(i.price_paid or 0) for i in pending_items)
    family_header = t("family_cart_badge", lang) if is_family else ""

    lines = [
        f"{t('checklist_title', lang)}{family_header}",
        t("items_remaining", lang, pending=len(pending_items), purchased=len(purchased_items)),
    ]
    if total_est > 0:
        lines.append(f"{t('total_estimate', lang, total=f'{total_est:,.0f}')}\n")
    else:
        lines.append("")

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
        lines.append(t("purchased_section", lang))
        for pit in purchased_items[:6]:
            lines.append(f"  <s>[x] {escape_html(pit.item_name)}</s>")

    action_row = [
        InlineKeyboardButton(text=t("share", lang), callback_data="share_family_cart"),
        InlineKeyboardButton(text=t("clear_done", lang), callback_data="chk_clear_done"),
    ]
    inline_rows.append(action_row)
    inline_rows.append([
        InlineKeyboardButton(
            text=t("open_webapp", lang),
            web_app=WebAppInfo(url=webapp_url),
        )
    ])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=inline_rows)


# ── /start Handler ──────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db_session: Any, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    settings = get_settings()
    user = message.from_user
    if user is None:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    webapp_url = settings.telegram_webapp_url.rstrip("/")
    user_lang = user.language_code or "ru"

    # Secure deep-link argument with owner approval and rate limit
    if command.args and command.args.startswith("cart_"):
        if not _check_join_rate_limit(user.id):
            await message.answer(t("family_rate_limit", user_lang))
            return

        target_cart_id_str = command.args.replace("cart_", "").strip()
        try:
            target_uuid = uuid.UUID(target_cart_id_str)
            if target_uuid != db_user.id:
                target_user = await session.get(User, target_uuid)
                if target_user is not None:
                    owner_chat_id = (
                        decrypt_telegram_id(target_user.telegram_id_encrypted, settings.secret_key)
                        if target_user.telegram_id_encrypted and settings.secret_key
                        else None
                    )
                    if owner_chat_id:
                        approval_kb = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text=t("approve", target_user.language_code),
                                        callback_data=f"cart_appr:{target_uuid}:{db_user.id}",
                                    ),
                                    InlineKeyboardButton(
                                        text=t("deny", target_user.language_code),
                                        callback_data=f"cart_deny:{target_uuid}:{db_user.id}",
                                    ),
                                ]
                            ]
                        )
                        requester_name = escape_html(user.first_name or "Пользователь")
                        if user.username:
                            requester_name += f" (@{escape_html(user.username)})"
                        try:
                            await bot.send_message(
                                chat_id=owner_chat_id,
                                text=t("family_join_request_owner", target_user.language_code, requester=requester_name),
                                reply_markup=approval_kb,
                                parse_mode=ParseMode.HTML,
                            )
                            await message.answer(t("family_join_request_sent", user_lang), parse_mode=ParseMode.HTML)
                        except Exception as exc:
                            logger.warning("Could not send join request to owner: %s", exc)
                            db_user.family_cart_id = target_uuid
                            await session.commit()
                            await message.answer(t("family_join_approved_member", user_lang), parse_mode=ParseMode.HTML)
                    else:
                        db_user.family_cart_id = target_uuid
                        await session.commit()
                        await message.answer(t("family_join_approved_member", user_lang), parse_mode=ParseMode.HTML)
        except (ValueError, TypeError) as exc:
            logger.warning("Invalid family cart deep-link: %s", exc)

    safe_first_name = escape_html(user.first_name or "Пользователь")
    welcome_text = t("welcome", user_lang, name=safe_first_name)

    reply_kb = get_main_reply_keyboard(webapp_url, user_lang)
    chk_text, chk_kb = await render_checklist_message(session, db_user, webapp_url)

    await message.answer(welcome_text, reply_markup=reply_kb, parse_mode=ParseMode.HTML)
    await message.answer(chk_text, reply_markup=chk_kb, parse_mode=ParseMode.HTML)


# ── Family Cart Approval Callbacks ──────────────────────────────────────────

@router.callback_query(F.data.startswith("cart_appr:"))
async def cb_approve_join(callback: CallbackQuery, db_session: Any, bot: Bot) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    if not user:
        return
    db_user = await get_or_create_user(session, user)
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    cart_uuid_str, requester_uuid_str = parts[1], parts[2]

    # Verify that caller is the owner of the cart
    if str(db_user.id) != cart_uuid_str and str(db_user.family_cart_id) != cart_uuid_str:
        await callback.answer("У вас нет прав на управление этой корзиной", show_alert=True)
        return

    try:
        requester_uuid = uuid.UUID(requester_uuid_str)
        cart_uuid = uuid.UUID(cart_uuid_str)
        requester = await session.get(User, requester_uuid)
        if requester:
            requester.family_cart_id = cart_uuid
            await session.commit()

            if requester.telegram_id_encrypted:
                settings = get_settings()
                req_chat_id = decrypt_telegram_id(requester.telegram_id_encrypted, settings.secret_key)
                if req_chat_id:
                    try:
                        await bot.send_message(
                            chat_id=req_chat_id,
                            text=t("family_join_approved_member", requester.language_code),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception as e:
                        logger.warning("Could not notify requester of approval: %s", e)

            req_name = escape_html(requester.first_name or "Пользователь")
            owner_text = t("family_join_approved_owner", db_user.language_code, requester=req_name)
            await callback.answer()
            if callback.message:
                await callback.message.edit_text(owner_text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error approving cart join: %s", exc)
        await callback.answer("Ошибка обработки запроса")


@router.callback_query(F.data.startswith("cart_deny:"))
async def cb_deny_join(callback: CallbackQuery, db_session: Any, bot: Bot) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    if not user:
        return
    db_user = await get_or_create_user(session, user)
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    cart_uuid_str, requester_uuid_str = parts[1], parts[2]

    if str(db_user.id) != cart_uuid_str and str(db_user.family_cart_id) != cart_uuid_str:
        await callback.answer("У вас нет прав на управление этой корзиной", show_alert=True)
        return

    try:
        requester_uuid = uuid.UUID(requester_uuid_str)
        requester = await session.get(User, requester_uuid)
        if requester and requester.telegram_id_encrypted:
            settings = get_settings()
            req_chat_id = decrypt_telegram_id(requester.telegram_id_encrypted, settings.secret_key)
            if req_chat_id:
                try:
                    await bot.send_message(
                        chat_id=req_chat_id,
                        text=t("family_join_denied_member", requester.language_code),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.warning("Could not notify requester of denial: %s", e)

        owner_text = t("family_join_denied_owner", db_user.language_code)
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(owner_text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error denying cart join: %s", exc)
        await callback.answer("Ошибка обработки запроса")


# ── Help & Back Callbacks ────────────────────────────────────────────────────

@router.callback_query(F.data == "view_bot_help")
async def handle_bot_help(callback: CallbackQuery) -> None:
    await callback.answer()
    user_lang = callback.from_user.language_code or "ru" if callback.from_user else "ru"
    help_text = t("help_text", user_lang)
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("back_to_menu", user_lang), callback_data="back_to_main_menu")]
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
    lang = callback.from_user.language_code or "ru" if callback.from_user else "ru"
    cancel_msg = t("action_cancelled", lang)
    await callback.answer(cancel_msg)
    if not callback.message or not callback.from_user:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, callback.from_user)
    settings = get_settings()

    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    try:
        await callback.message.edit_text(
            f"{cancel_msg}\n\n{text}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.error("Error on cancel: %s", exc)


# ── Quick Bottom Menu Actions ────────────────────────────────────────────────

@router.message(F.text.in_({"📋 Мой список", "📋 Mening ro'yxatim", "📋 My checklist", "📋 Чек-лист покупок"}))
async def msg_show_checklist(message: Message, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = message.from_user
    if not user:
        return
    db_user = await get_or_create_user(session, user)
    settings = get_settings()

    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.message(F.text.in_({"🛒 Добавить регулярные", "🛒 Doimiy mahsulotlar", "🛒 Add staples", "🛒 Регулярные товары", "💡 Регулярные товары"}))
async def msg_add_staples(message: Message, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = message.from_user
    if not user:
        return
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)
    lang = user.language_code or "ru"

    staples = [
        {"name": "Говядина мякоть", "qty": 1.5, "unit": "кг", "category": "🥩 Мясной отдел", "price": 135000},
        {"name": "Картофель", "qty": 3.0, "unit": "кг", "category": "🥦 Овощные ряды", "price": 15000},
        {"name": "Лук репчатый", "qty": 2.0, "unit": "кг", "category": "🥦 Овощные ряды", "price": 6000},
        {"name": "Масло растительное", "qty": 1.0, "unit": "л", "category": "🥫 Бакалея и специи", "price": 19000},
        {"name": "Хлеб / Лепешки", "qty": 2.0, "unit": "шт", "category": "🍞 Лепешки и выпечка", "price": 8000},
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
            city="Ташкент",
            is_purchased=False,
        )
        session.add(p)
        added += 1

    await session.commit()
    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)

    await message.answer(t("staples_added", lang, count=added), parse_mode=ParseMode.HTML)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Voice Message Handler ───────────────────────────────────────────────────

@router.message(F.voice | F.audio)
async def handle_voice_message(message: Message, db_session: Any, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)
    lang = user.language_code or "ru"

    status_msg = await message.answer(t("voice_processing", lang), parse_mode=ParseMode.HTML)

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_bytes)
        audio_data = file_bytes.getvalue()

        async with BAIClient() as client:
            transcription = await client.transcribe_audio(audio_data, filename="voice.ogg")

        if not transcription:
            await status_msg.edit_text(t("voice_empty", lang))
            return

        safe_transcript = escape_html(transcription)
        await status_msg.edit_text(f"🗣 <i>«{safe_transcript}»</i>\n✨ <b>Добавляю в список...</b>", parse_mode=ParseMode.HTML)

        parse_result = await UniversalAIParser.parse_any_text(transcription)

        if not parse_result.items:
            await status_msg.edit_text(t("voice_no_items", lang, transcript=safe_transcript))
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
                city="Ташкент",
                is_purchased=False,
            )
            session.add(p)

        await session.commit()
        settings = get_settings()
        text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)

        await status_msg.edit_text(t("voice_added", lang, count=len(parse_result.items)), parse_mode=ParseMode.HTML)
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    except Exception as exc:
        logger.exception("Voice handling error: %s", exc)
        await status_msg.edit_text(t("voice_error", lang))


# ── Text & Recipe Handler ────────────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_or_recipe(message: Message, db_session: Any) -> None:
    user = message.from_user
    text = message.text
    if not user or not text:
        return

    session: AsyncSession = db_session
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)
    lang = user.language_code or "ru"

    is_recipe = any(
        w in text.lower()
        for w in ["рецепт", "ингредиент", "порци", "приготовлени", "youtube.com", "youtu.be", "плов", "шурпа", "лагман", "манты"]
    )

    status_msg = await message.answer(t("text_processing", lang), parse_mode=ParseMode.HTML)

    try:
        if is_recipe:
            parse_result = await UniversalAIParser.parse_recipe(text, servings=4)
        else:
            parse_result = await UniversalAIParser.parse_any_text(text)

        if not parse_result.items:
            await status_msg.edit_text(t("text_no_items", lang))
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
                city="Ташкент",
                is_purchased=False,
            )
            session.add(p)
            added_count += 1

        await session.commit()
        settings = get_settings()
        chk_text, chk_kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)

        tag = "по рецепту" if is_recipe else "в список"
        await status_msg.edit_text(t("text_added", lang, tag=tag, count=added_count), parse_mode=ParseMode.HTML)
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
    lang = user.language_code or "ru"

    await session.execute(
        delete(PurchaseHistory).where(
            PurchaseHistory.user_id == cart_id,
            PurchaseHistory.is_purchased == True,  # noqa: E712
        )
    )
    await session.commit()
    await callback.answer(t("items_cleared", lang))

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
    lang = user.language_code or "ru"

    share_link = f"https://t.me/gusop_bot?start=cart_{str(db_user.id)}"
    msg = t("family_share_msg", lang, link=share_link)

    await callback.answer()
    if callback.message:
        await callback.message.answer(msg, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "add_staples_quick")
async def cb_add_staples_quick(callback: CallbackQuery, db_session: Any) -> None:
    session: AsyncSession = db_session
    user = callback.from_user
    db_user = await get_or_create_user(session, user)
    cart_id = get_effective_cart_id(db_user)
    lang = user.language_code or "ru"

    staples = [
        ("Говядина мякоть", 1.5, "кг", "🥩 Мясной отдел", 135000),
        ("Картофель", 3.0, "кг", "🥦 Овощные ряды", 15000),
        ("Лук репчатый", 2.0, "кг", "🥦 Овощные ряды", 6000),
        ("Масло растительное", 1.0, "л", "🥫 Бакалея и специи", 19000),
        ("Хлеб / Лепешки", 2.0, "шт", "🍞 Лепешки и выпечка", 8000),
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
            city="Ташкент",
            is_purchased=False,
        )
        session.add(p)

    await session.commit()
    await callback.answer(t("staples_added", lang, count=len(staples)))

    settings = get_settings()
    text, kb = await render_checklist_message(session, db_user, settings.telegram_webapp_url)
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.error("Error editing staples message: %s", exc)
