"""
OmniCart AI — Cryptographic Security & Telegram WebApp Validation Module.
Provides HMAC-SHA256 signature verification for Telegram Mini App initData,
replay attack protection, and typed data transfer objects.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, unquote

from pydantic import BaseModel, Field, ValidationError


class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = False
    allows_write_to_pm: Optional[bool] = False


class ValidatedInitData(BaseModel):
    query_id: Optional[str] = None
    user: TelegramUser
    auth_date: int
    hash: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class SecurityValidationError(Exception):
    """Raised when Telegram initData fails cryptographic or timestamp verification."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TelegramSecurityValidator:
    """
    Validates Telegram WebApp initData query strings against the bot token.
    Follows official Telegram Bot API specification:
    1. Secret key = HMAC-SHA256("WebAppData", bot_token)
    2. Data check string = sorted alphabetically key=value lines without hash
    3. Hash = HMAC-SHA256(secret_key, data_check_string).hexdigest()
    """

    def __init__(self, bot_token: str, max_auth_age_seconds: int = 86400):
        if not bot_token:
            raise ValueError("bot_token must not be empty")
        self._bot_token = bot_token
        self._max_auth_age_seconds = max_auth_age_seconds
        self._secret_key = self._generate_secret_key(bot_token)

    @staticmethod
    def _generate_secret_key(token: str) -> bytes:
        return hmac.new(
            key=b"WebAppData",
            msg=token.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

    def validate_init_data(self, init_data_raw: str) -> ValidatedInitData:
        if not init_data_raw or not init_data_raw.strip():
            raise SecurityValidationError("Строка initData пуста.")

        try:
            parsed_pairs = dict(parse_qsl(init_data_raw, keep_blank_values=True, strict_parsing=True))
        except ValueError as exc:
            raise SecurityValidationError(f"Некорректный формат строки запроса: {str(exc)}") from exc

        if "hash" not in parsed_pairs:
            raise SecurityValidationError("В переданных данных отсутствует обязательный параметр 'hash'.")

        received_hash = parsed_pairs.pop("hash")

        data_check_list = []
        for key in sorted(parsed_pairs.keys()):
            data_check_list.append(f"{key}={parsed_pairs[key]}")
        data_check_string = "\n".join(data_check_list)

        calculated_hash = hmac.new(
            key=self._secret_key,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise SecurityValidationError("Криптографическая подпись данных Telegram не совпадает.")

        if "auth_date" not in parsed_pairs:
            raise SecurityValidationError("В переданных данных отсутствует 'auth_date'.")

        try:
            auth_date = int(parsed_pairs["auth_date"])
        except ValueError as exc:
            raise SecurityValidationError("Параметр 'auth_date' должен быть целым числом.") from exc

        current_timestamp = int(time.time())
        if current_timestamp - auth_date > self._max_auth_age_seconds:
            raise SecurityValidationError(
                f"Срок действия авторизации истек (возраст: {current_timestamp - auth_date} сек, "
                f"максимум: {self._max_auth_age_seconds} сек)."
            )

        if auth_date > current_timestamp + 60:
            raise SecurityValidationError("Дата авторизации находится в будущем.")

        if "user" not in parsed_pairs:
            raise SecurityValidationError("В initData отсутствуют данные о пользователе ('user').")

        try:
            user_dict = json.loads(unquote(parsed_pairs["user"]))
            validated_user = TelegramUser.model_validate(user_dict)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SecurityValidationError(f"Невалидные данные пользователя внутри initData: {str(exc)}") from exc

        return ValidatedInitData(
            query_id=parsed_pairs.get("query_id"),
            user=validated_user,
            auth_date=auth_date,
            hash=received_hash,
            raw_data=parsed_pairs,
        )
