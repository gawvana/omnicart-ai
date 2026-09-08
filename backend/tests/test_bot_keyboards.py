"""
Unit tests for Telegram bot keyboards and i18n localization.
Ensures zero callback_query_data typos, complete translations, and terminology consistency.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from bot.i18n import STRINGS, t
from bot.handlers.start import (
    build_main_inline_keyboard,
    build_cancel_keyboard,
    get_main_reply_keyboard,
)


class TestBotKeyboards(unittest.TestCase):
    """Test suite for inline and reply keyboard constructors."""

    def test_main_inline_keyboard_structure(self):
        test_url = "https://omnicart.vercel.app"
        for lang in ["ru", "uz", "en"]:
            kb = build_main_inline_keyboard(test_url, current_lang=lang)
            self.assertIsNotNone(kb.inline_keyboard)
            self.assertGreaterEqual(len(kb.inline_keyboard), 2)

            for row in kb.inline_keyboard:
                for btn in row:
                    # Guard against callback_query_data typo bug
                    self.assertFalse(hasattr(btn, "callback_query_data"), "Found forbidden callback_query_data attribute")
                    # Button must have url, web_app, or callback_data
                    has_action = btn.url is not None or btn.web_app is not None or btn.callback_data is not None
                    self.assertTrue(has_action, f"Button '{btn.text}' has no interaction payload")

    def test_cancel_keyboard_callback(self):
        for lang in ["ru", "uz", "en"]:
            kb = build_cancel_keyboard(current_lang=lang)
            self.assertEqual(len(kb.inline_keyboard), 1)
            btn = kb.inline_keyboard[0][0]
            self.assertEqual(btn.callback_data, "cancel_action")
            self.assertFalse(hasattr(btn, "callback_query_data"))

    def test_reply_keyboard_rows(self):
        test_url = "https://omnicart.vercel.app"
        for lang in ["ru", "uz", "en"]:
            kb = get_main_reply_keyboard(test_url, current_lang=lang)
            self.assertGreaterEqual(len(kb.keyboard), 2)
            self.assertTrue(kb.is_persistent)
            self.assertTrue(kb.resize_keyboard)


class TestBotI18n(unittest.TestCase):
    """Test suite for internationalization completeness and formatting."""

    def test_all_keys_have_three_languages(self):
        languages = ["ru", "uz", "en"]
        for key, translations in STRINGS.items():
            for lang in languages:
                self.assertIn(lang, translations, f"Key '{key}' is missing translation for '{lang}'")
                self.assertTrue(len(translations[lang]) > 0, f"Translation for '{key}' in '{lang}' is empty")

    def test_t_helper_fallback(self):
        # Non-existent key falls back to key itself
        self.assertEqual(t("non_existent_key_xyz", "ru"), "non_existent_key_xyz")
        # Sub-locale matching (e.g. uz-UZ -> uz)
        self.assertIn("Ro'yxat", t("open_app", "uz-UZ"))
        # Fallback to ru if key exists
        self.assertIn("Открыть", t("open_app", "de"))

    def test_parameterized_keys(self):
        # Welcome message parameter
        welcome_ru = t("welcome", "ru", name="Aziz")
        self.assertIn("Aziz", welcome_ru)

        # Items remaining parameter
        rem_uz = t("items_remaining", "uz", pending=3, purchased=5)
        self.assertIn("3", rem_uz)
        self.assertIn("5", rem_uz)

        # Total estimate must use unified "Итого" terminology
        total_ru = t("total_estimate", "ru", total="45,000")
        self.assertIn("Итого:", total_ru)
        self.assertNotIn("Общая сумма", total_ru)


if __name__ == "__main__":
    unittest.main()
