"""
Automated unit test suite verifying OmniCart AI modernization.
Tests Telegram initData cryptographic validation, bot keyboards, deep-link handling, and API routes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from core.security import (
    SecurityValidationError,
    TelegramSecurityValidator,
    TelegramUser,
)
from database.models import PurchaseHistory, User, UserSettings
from bot.handlers.start import (
    BOT_STRINGS,
    t,
    build_main_inline_keyboard,
    build_cancel_keyboard,
    get_main_reply_keyboard,
)


def test_telegram_security_validator():
    bot_token = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz12345678"
    validator = TelegramSecurityValidator(bot_token=bot_token, max_auth_age_seconds=3600)

    # Build valid initData
    user_data = {
        "id": 987654321,
        "first_name": "Aziz",
        "last_name": "Karimov",
        "username": "aziz_k",
        "language_code": "uz",
    }
    user_json = json.dumps(user_data, separators=(",", ":"))
    auth_date = str(int(time.time()))

    pairs = {
        "auth_date": auth_date,
        "query_id": "AAHdF6IQAAAAAN0XohC0-gS-",
        "user": user_json,
    }

    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    correct_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    raw_init_data = f"auth_date={auth_date}&hash={correct_hash}&query_id=AAHdF6IQAAAAAN0XohC0-gS-&user={user_json}"

    # Test 1: Successful validation
    validated = validator.validate_init_data(raw_init_data)
    assert validated.user.id == 987654321
    assert validated.user.first_name == "Aziz"
    assert validated.auth_date == int(auth_date)
    print("[PASS] Test 1: Valid initData successfully authenticated.")

    # Test 2: Tampered hash rejection
    tampered_init_data = raw_init_data.replace(correct_hash, "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
    try:
        validator.validate_init_data(tampered_init_data)
        assert False, "Tampered initData should have failed validation!"
    except SecurityValidationError:
        print("[PASS] Test 2: Tampered hash correctly rejected.")

    # Test 3: Expired auth_date rejection
    expired_validator = TelegramSecurityValidator(bot_token=bot_token, max_auth_age_seconds=10)
    time.sleep(0.01)
    expired_auth_date = str(int(time.time()) - 100)
    exp_pairs = {
        "auth_date": expired_auth_date,
        "user": user_json,
    }
    exp_check_string = "\n".join(f"{k}={exp_pairs[k]}" for k in sorted(exp_pairs.keys()))
    exp_hash = hmac.new(secret_key, exp_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    expired_raw = f"auth_date={expired_auth_date}&hash={exp_hash}&user={user_json}"
    try:
        expired_validator.validate_init_data(expired_raw)
        assert False, "Expired initData should have failed validation!"
    except SecurityValidationError:
        print("[PASS] Test 3: Expired initData correctly rejected.")


def test_bot_keyboards_and_no_callback_query_data():
    """Verify inline keyboards use callback_data and have no callback_query_data bugs."""
    for lang in ["ru", "uz", "en"]:
        kb_main = build_main_inline_keyboard("https://omnicart-ai.vercel.app", lang)
        for row in kb_main.inline_keyboard:
            for btn in row:
                assert not hasattr(btn, "callback_query_data"), "Found forbidden callback_query_data attribute!"
                if btn.url is None and btn.web_app is None:
                    assert btn.callback_data is not None, f"Button {btn.text} has neither URL nor callback_data!"

        kb_cancel = build_cancel_keyboard(lang)
        for row in kb_cancel.inline_keyboard:
            for btn in row:
                assert not hasattr(btn, "callback_query_data")
                assert btn.callback_data is not None

        reply_kb = get_main_reply_keyboard("https://omnicart-ai.vercel.app", lang)
        assert len(reply_kb.keyboard) >= 2

    print("[PASS] Test 4: All bot inline keyboards verified (0 callback_query_data typos, all callback_data valid).")


def test_bot_localization_consistency():
    """Verify all required localized strings exist for ru, uz, en."""
    for key in BOT_STRINGS:
        for lang in ["ru", "uz", "en"]:
            text = t(key, lang)
            assert text and len(text) > 0, f"Missing localization for '{key}' in lang '{lang}'"

    print("[PASS] Test 5: Bot localization strings complete and consistent across ru, uz, en.")


def test_models_and_indexes():
    assert hasattr(PurchaseHistory, "item_name")
    assert hasattr(PurchaseHistory, "quantity")
    assert hasattr(PurchaseHistory, "price_paid")
    assert hasattr(PurchaseHistory, "is_purchased")
    assert hasattr(User, "telegram_id_hash")
    assert hasattr(User, "family_cart_id")

    purch_args = PurchaseHistory.__table_args__
    assert any(getattr(idx, "name", None) == "ix_purchase_item_created" for idx in purch_args)
    assert any(getattr(idx, "name", None) == "ix_purchase_product_created" for idx in purch_args)
    print("[PASS] Test 6: Database models and composite indexes verified.")


def test_modular_api_routes():
    from api.main import app

    routes = list(app.openapi().get("paths", {}).keys())
    expected_routes = [
        "/api/v1/checklist",
        "/api/v1/checklist/{item_id}/toggle",
        "/api/v1/checklist/{item_id}",
        "/api/v1/checklist/clear-purchased",
        "/api/v1/cart/join-family",
        "/api/v1/ai/parse-text",
        "/api/v1/ai/parse-recipe",
        "/api/v1/notes/import-xiaomi",
        "/api/v1/profile",
        "/api/v1/settings",
        "/api/webhook",
        "/api/health",
        "/health",
    ]

    for er in expected_routes:
        assert er in routes, f"Missing expected route {er} in FastAPI application!"
    print(f"[PASS] Test 7: All {len(expected_routes)} modular endpoints registered in FastAPI.")


if __name__ == "__main__":
    print("Running OmniCart AI Modernization Test Suite...\n")
    test_telegram_security_validator()
    test_bot_keyboards_and_no_callback_query_data()
    test_bot_localization_consistency()
    test_models_and_indexes()
    test_modular_api_routes()
    print("\nAll modernization tests PASSED successfully!")
