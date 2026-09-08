"""
OmniCart AI — Centralized Bot Internationalization (i18n) Module.
Provides translations for Russian, Uzbek, and English across all bot messages,
inline keyboards, and notification strings.
"""

from __future__ import annotations

from typing import Any

STRINGS: dict[str, dict[str, str]] = {
    # ── Keyboards & Buttons ───────────────────────────────────────────────────
    "open_app": {
        "ru": "🛍 Открыть список",
        "uz": "🛍 Ro'yxatni ochish",
        "en": "🛍 Open checklist",
    },
    "help": {
        "ru": "ℹ️ Справка",
        "uz": "ℹ️ Yordam",
        "en": "ℹ️ Help",
    },
    "cancel": {
        "ru": "❌ Отмена",
        "uz": "❌ Bekor qilish",
        "en": "❌ Cancel",
    },
    "my_list": {
        "ru": "📋 Мой список",
        "uz": "📋 Mening ro'yxatim",
        "en": "📋 My checklist",
    },
    "add_staples": {
        "ru": "🛒 Регулярные товары",
        "uz": "🛒 Doimiy mahsulotlar",
        "en": "🛒 Add staples",
    },
    "open_webapp": {
        "ru": "🚀 В приложение",
        "uz": "🚀 Ilovaga o'tish",
        "en": "🚀 Open app",
    },
    "share": {
        "ru": "🔗 Поделиться",
        "uz": "🔗 Ulashish",
        "en": "🔗 Share",
    },
    "clear_done": {
        "ru": "🗑 Очистить купленное",
        "uz": "🗑 Xaridlarni tozalash",
        "en": "🗑 Clear done",
    },
    "back_to_menu": {
        "ru": "⬅️ В меню",
        "uz": "⬅️ Menyuga",
        "en": "⬅️ Back to menu",
    },
    "approve": {
        "ru": "✅ Разрешить",
        "uz": "✅ Ruxsat berish",
        "en": "✅ Approve",
    },
    "deny": {
        "ru": "❌ Отклонить",
        "uz": "❌ Rad etish",
        "en": "❌ Deny",
    },

    # ── Empty List ───────────────────────────────────────────────────────────
    "empty_list": {
        "ru": (
            "📋 <b>Список покупок пуст</b>\n\n"
            "Как добавить товары:\n"
            "• 🎙 Голосовое: <i>«2 кг картошки и хлеб»</i>\n"
            "• 📝 Любой текст или список из Заметок\n"
            "• Нажмите <b>«🛒 Регулярные товары»</b> ниже"
        ),
        "uz": (
            "📋 <b>Xaridlar ro'yxati bo'sh</b>\n\n"
            "Mahsulot qo'shish usullari:\n"
            "• 🎙 Ovozli xabar: <i>«2 kg kartoshka va non»</i>\n"
            "• 📝 Matn yoki eslatmalardan ro'yxat\n"
            "• Pastdagi <b>«🛒 Doimiy mahsulotlar»</b> tugmasini bosing"
        ),
        "en": (
            "📋 <b>Shopping checklist is empty</b>\n\n"
            "How to add items:\n"
            "• 🎙 Voice note: <i>\"2 kg potatoes and bread\"</i>\n"
            "• 📝 Any text or pasted checklist\n"
            "• Tap <b>\"🛒 Add staples\"</b> below"
        ),
    },

    # ── Welcome ──────────────────────────────────────────────────────────────
    "welcome": {
        "ru": (
            "👋 Здравствуйте, <b>{name}</b>!\n\n"
            "<b>OmniCart AI</b> — умный ассистент для списков покупок.\n\n"
            "Возможности:\n"
            "• 🎙 <b>Голосовой ввод</b> — надиктуйте список покупок\n"
            "• 📝 <b>Текст и рецепты</b> — перешлите заметку или рецепт\n"
            "• 👥 <b>Семейная корзина</b> — совместные покупки в реальном времени"
        ),
        "uz": (
            "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
            "<b>OmniCart AI</b> — qulay oilaviy xaridlar yordamchisi.\n\n"
            "Imkoniyatlar:\n"
            "• 🎙 <b>Ovozli xabar</b> — xaridlarni ovoz orqali ayting\n"
            "• 📝 <b>Matn va retseptlar</b> — eslatmalar va retseptlarni yuboring\n"
            "• 👥 <b>Oilaviy savat</b> — birgalikda real vaqtda xarid qiling"
        ),
        "en": (
            "👋 Hello, <b>{name}</b>!\n\n"
            "<b>OmniCart AI</b> — smart shopping assistant for your family.\n\n"
            "Features:\n"
            "• 🎙 <b>Voice input</b> — dictate your grocery items\n"
            "• 📝 <b>Text & recipes</b> — paste any note or recipe\n"
            "• 👥 <b>Family cart</b> — shop together in real time"
        ),
    },

    # ── Help ─────────────────────────────────────────────────────────────────
    "help_text": {
        "ru": (
            "ℹ️ <b>Справка OmniCart AI:</b>\n\n"
            "• 🎙 Отправьте голосовое сообщение для мгновенного добавления товаров.\n"
            "• 📝 Скопируйте любой текст или рецепт в чат — продукты определятся автоматически.\n"
            "• 🚀 Нажмите <b>«В приложение»</b> для быстрого интерактивного чек-листа.\n"
            "• 🔗 Нажмите <b>«Поделиться»</b> для подключения членов семьи к корзине."
        ),
        "uz": (
            "ℹ️ <b>OmniCart AI bo'yicha qo'llanma:</b>\n\n"
            "• 🎙 Mahsulotlarni darhol qo'shish uchun ovozli xabar yuboring.\n"
            "• 📝 Har qanday matn yoki retsept yuboring — mahsulotlar avtomatik aniqlanadi.\n"
            "• 🚀 Interaktiv чек-лист uchun <b>«Ilovaga o'tish»</b> tugmasini bosing.\n"
            "• 🔗 Oila a'zolarini ulash uchun <b>«Ulashish»</b> tugmasini bosing."
        ),
        "en": (
            "ℹ️ <b>OmniCart AI Help:</b>\n\n"
            "• 🎙 Send a voice note to add groceries instantly.\n"
            "• 📝 Paste any text or recipe — items will be parsed automatically.\n"
            "• 🚀 Tap <b>\"Open app\"</b> for an interactive checklist.\n"
            "• 🔗 Tap <b>\"Share\"</b> to sync with your family in real time."
        ),
    },

    # ── Checklist Headings & Status ──────────────────────────────────────────
    "checklist_title": {
        "ru": "📋 <b>Список покупок</b>",
        "uz": "📋 <b>Xaridlar ro'yxati</b>",
        "en": "📋 <b>Shopping checklist</b>",
    },
    "family_cart_badge": {
        "ru": " 👥 (Семейная корзина)",
        "uz": " 👥 (Oilaviy savat)",
        "en": " 👥 (Family cart)",
    },
    "items_remaining": {
        "ru": "Осталось: <b>{pending}</b> | Куплено: {purchased}",
        "uz": "Qoldi: <b>{pending}</b> | Xarid qilindi: {purchased}",
        "en": "Pending: <b>{pending}</b> | Done: {purchased}",
    },
    "total_estimate": {
        "ru": "Итого: <b>{total}</b> сум",
        "uz": "Jami: <b>{total}</b> so'm",
        "en": "Total: <b>{total}</b> UZS",
    },
    "purchased_section": {
        "ru": "<b>Куплено:</b>",
        "uz": "<b>Xarid qilinganlar:</b>",
        "en": "<b>Purchased:</b>",
    },
    "action_cancelled": {
        "ru": "❌ Действие отменено.",
        "uz": "❌ Amal bekor qilindi.",
        "en": "❌ Action cancelled.",
    },

    # ── Voice / Text Parsing ─────────────────────────────────────────────────
    "voice_processing": {
        "ru": "🎙 <i>Распознаю аудиозапись...</i>",
        "uz": "🎙 <i>Ovoz yozuvi aniqlanmoqda...</i>",
        "en": "🎙 <i>Processing voice note...</i>",
    },
    "voice_empty": {
        "ru": "❌ Не удалось разобрать аудио. Попробуйте наговорить четче или отправьте текстом.",
        "uz": "❌ Ovozni aniqlab bo'lmadi. Aniqroq gapiring yoki matn yuboring.",
        "en": "❌ Could not recognize audio. Please speak clearly or send text.",
    },
    "voice_no_items": {
        "ru": "🤔 Распознано: «{transcript}», но товары не найдены. Назовите продукты.",
        "uz": "🤔 Eshitildi: «{transcript}», lekin mahsulotlar topilmadi. Mahsulot nomlarini ayting.",
        "en": "🤔 Heard: \"{transcript}\", but no grocery items detected.",
    },
    "voice_added": {
        "ru": "✅ Добавлено из голоса: <b>{count}</b> поз.",
        "uz": "✅ Ovoz orqali qo'shildi: <b>{count}</b> ta",
        "en": "✅ Added from voice: <b>{count}</b> items",
    },
    "voice_error": {
        "ru": "❌ Ошибка при обработке аудио. Попробуйте отправить текстом.",
        "uz": "❌ Ovozni qayta ishlashda xatolik. Matn orqali yuborib ko'ring.",
        "en": "❌ Voice processing error. Please try sending text.",
    },
    "text_processing": {
        "ru": "✨ <i>Разбираю запись...</i>",
        "uz": "✨ <i>Yozuv tahlil qilinmoqda...</i>",
        "en": "✨ <i>Analyzing text...</i>",
    },
    "text_no_items": {
        "ru": "🤔 Не удалось распознать товары. Напишите продукты, например: «картошка 2кг, мясо 1кг».",
        "uz": "🤔 Mahsulotlar aniqlanmadi. Masalan: «2 kg kartoshka, 1 kg go'sht» shaklida yozing.",
        "en": "🤔 No grocery items found. For example: \"2 kg potatoes, 1 kg meat\".",
    },
    "text_added": {
        "ru": "✅ Добавлено {tag}: <b>{count}</b> поз.!",
        "uz": "✅ Qo'shildi ({tag}): <b>{count}</b> ta!",
        "en": "✅ Added {tag}: <b>{count}</b> items!",
    },
    "staples_added": {
        "ru": "✅ Добавлено <b>{count}</b> регулярных товаров!",
        "uz": "✅ <b>{count}</b> ta doimiy mahsulot qo'shildi!",
        "en": "✅ Added <b>{count}</b> staple items!",
    },
    "items_cleared": {
        "ru": "Купленные товары удалены",
        "uz": "Xarid qilingan mahsulotlar tozalandi",
        "en": "Purchased items cleared",
    },

    # ── Family Cart ──────────────────────────────────────────────────────────
    "family_share_msg": {
        "ru": (
            "🔗 <b>Ссылка на семейную корзину:</b>\n\n"
            "<code>{link}</code>\n\n"
            "Отправьте эту ссылку близким. При переходе владелец получит запрос на подключение."
        ),
        "uz": (
            "🔗 <b>Oilaviy savat havolasi:</b>\n\n"
            "<code>{link}</code>\n\n"
            "Bu havolani yaqinlaringizga yuboring. Ular o'tganda egasiga so'rov keladi."
        ),
        "en": (
            "🔗 <b>Family cart link:</b>\n\n"
            "<code>{link}</code>\n\n"
            "Share this link with family members. The cart owner will receive a connection request."
        ),
    },
    "family_join_request_owner": {
        "ru": "👥 Пользователь <b>{requester}</b> хочет подключиться к вашей семейной корзине. Разрешить?",
        "uz": "👥 Foydalanuvchi <b>{requester}</b> oilaviy savatingizga ulanmoqchi. Ruxsat berasizmi?",
        "en": "👥 User <b>{requester}</b> wants to join your family cart. Allow?",
    },
    "family_join_request_sent": {
        "ru": "⏳ Запрос на подключение отправлен владельцу корзины. Ожидайте подтверждения.",
        "uz": "⏳ Savat egasiga ulanish so'rovi yuborildi. Tasdiqni kuting.",
        "en": "⏳ Connection request sent to the cart owner. Waiting for approval.",
    },
    "family_join_approved_owner": {
        "ru": "✅ Вы разрешили подключение пользователю <b>{requester}</b>.",
        "uz": "✅ Foydalanuvchi <b>{requester}</b> ga ruxsat berildi.",
        "en": "✅ You approved connection for <b>{requester}</b>.",
    },
    "family_join_approved_member": {
        "ru": "🎉 Владелец подтвердил подключение! Ваши списки покупок синхронизированы.",
        "uz": "🎉 Savat egasi ulanishni tasdiqladi! Xaridlar ro'yxatingiz sinxronlandi.",
        "en": "🎉 Cart owner approved your request! Your shopping lists are now synced.",
    },
    "family_join_denied_owner": {
        "ru": "❌ Запрос на подключение отклонён.",
        "uz": "❌ Ulanish so'rovi rad etildi.",
        "en": "❌ Connection request denied.",
    },
    "family_join_denied_member": {
        "ru": "Владелец отклонил запрос на подключение к семейной корзине.",
        "uz": "Savat egasi ulanish so'rovini rad etdi.",
        "en": "The cart owner declined the connection request.",
    },
    "family_rate_limit": {
        "ru": "Слишком много попыток подключения. Попробуйте позже.",
        "uz": "Ulanish urinishlari juda ko'p. Keyinroq urinib ko'ring.",
        "en": "Too many join attempts. Please try again later.",
    },
}


def t(key: str, lang: str = "ru", **kwargs: Any) -> str:
    """
    Retrieve localized string for `key` and `lang` with fallback to 'ru'.
    Optionally formats with `kwargs`.
    """
    lang_key = "uz" if lang.startswith("uz") else ("en" if lang.startswith("en") else "ru")
    bucket = STRINGS.get(key, {})
    template = bucket.get(lang_key, bucket.get("ru", key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
