"""
Automated unit test suite verifying OmniCart AI modernization.
"""

import hashlib
import hmac
import json
import sys
import time
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
from database.models import Base, PriceHistory, PurchaseHistory
from services.guliston_market_service import GulistonMarketService, MarketPriceEstimate


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
    print("[PASS] Test 1 Passed: Valid initData successfully authenticated.")

    # Test 2: Tampered hash rejection
    tampered_init_data = raw_init_data.replace(correct_hash, "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
    try:
        validator.validate_init_data(tampered_init_data)
        assert False, "Tampered initData should have failed validation!"
    except SecurityValidationError:
        print("[PASS] Test 2 Passed: Tampered hash correctly rejected.")

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
        print("[PASS] Test 3 Passed: Expired initData correctly rejected.")


def test_market_service_iqr_and_median():
    service = GulistonMarketService(session=None, redis=None)

    # Test dataset with obvious high outlier
    prices = [
        Decimal("4000.00"),
        Decimal("4200.00"),
        Decimal("4500.00"),
        Decimal("4600.00"),
        Decimal("4800.00"),
        Decimal("5000.00"),
        Decimal("99000.00"),  # Outlier
    ]

    cleaned = service._remove_outliers_iqr(sorted(prices))
    assert Decimal("99000.00") not in cleaned, "IQR outlier was not removed!"
    assert len(cleaned) == 6

    median = service._calculate_median(cleaned)
    assert median == Decimal("4550.00"), f"Expected median 4550.00, got {median}"
    print(f"[PASS] Test 4 Passed: IQR cleaned {len(prices)} -> {len(cleaned)} prices, median: {median} UZS.")


def test_models_and_indexes():
    # Verify PriceHistory and PurchaseHistory exist with required columns and table arguments
    assert hasattr(PriceHistory, "item_name")
    assert hasattr(PriceHistory, "price")
    assert hasattr(PriceHistory, "market_name")
    assert hasattr(PriceHistory, "created_at")

    table_args = PriceHistory.__table_args__
    assert any(getattr(idx, "name", None) == "ix_price_history_item_created" for idx in table_args)
    assert any(getattr(idx, "name", None) == "ix_price_history_market_created" for idx in table_args)

    purch_args = PurchaseHistory.__table_args__
    assert any(getattr(idx, "name", None) == "ix_purchase_item_created" for idx in purch_args)
    assert any(getattr(idx, "name", None) == "ix_purchase_product_created" for idx in purch_args)
    print("[PASS] Test 5 Passed: Models and composite indexes verified.")


def test_api_routes():
    from api.main import app

    routes = [r.path for r in app.routes]
    expected_routes = [
        "/api/v1/checklist",
        "/api/v1/checklist/{item_id}/toggle",
        "/api/v1/checklist/{item_id}",
        "/api/v1/checklist/clear-purchased",
        "/api/v1/market/estimate",
        "/api/v1/market/autocomplete",
        "/api/v1/market/report-price",
        "/api/webhook",
    ]

    for er in expected_routes:
        assert er in routes, f"Missing expected route {er} in FastAPI application!"
    print(f"[PASS] Test 6 Passed: All {len(expected_routes)} critical endpoints registered in FastAPI.")


if __name__ == "__main__":
    print("Running OmniCart AI Modernization Test Suite...\n")
    test_telegram_security_validator()
    test_market_service_iqr_and_median()
    test_models_and_indexes()
    test_api_routes()
    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (6/6)")
    print("==========================================")
