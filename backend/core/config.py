"""
OmniCart AI — Core configuration via Pydantic BaseSettings.
All secrets and tunables are loaded from environment / .env files.
Compatible with standard Docker environments and Vercel serverless functions.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Immutable, validated application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────────
    telegram_bot_token: str = Field(default="8889107787:AAG65uk0FfT3Yb54CeGV9SJPoi5ui8A1788", min_length=20)
    telegram_webapp_url: str = Field(default="https://omnicart-ai.vercel.app", min_length=8)
    telegram_webhook_secret: str = "e7b419c8d234a9f02345bcdef1289456"

    # ── Database ──────────────────────────────────────────────
    postgres_user: str = "omnicart"
    postgres_password: str = ""
    postgres_db: str = "omnicart_db"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: str = "sqlite+aiosqlite:///./omnicart.db"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "rediss://default:AZQPAAIgcDEzZjg4ODAxOGVhZGI0YTI2OTQ4OTBlNDY0ZmE0NjU5Mg@creative-possum-37903.upstash.io:6379"

    # ── B.AI API ──────────────────────────────────────────────
    bai_api_key: str = Field(default="sk-ifsmsa2do5for8wffu9ve8inj9sqggg7", min_length=3)
    bai_api_base: str = "https://api.b.ai/v1"
    bai_model: str = "deepseek-v4-flash"

    # ── Security ──────────────────────────────────────────────
    secret_key: str = Field(default="9f8b7c2d1e0a4f5b6c7d8e9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c", min_length=32)
    rate_limit_per_minute: int = 60
    cron_secret: str = "cron_8f93e10ab725c4819d45e02ba98f"
    telegram_initdata_max_age_seconds: int = 86400

    # ── Market & Pricing Configuration ────────────────────────
    market_price_cache_ttl_seconds: int = 3600
    market_estimate_lookback_days: int = 14

    # ── HTTP Client Timeouts ──────────────────────────────────
    http_client_timeout_seconds: float = 10.0
    http_client_read_timeout_seconds: float = 60.0

    # ── App ───────────────────────────────────────────────────
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    allowed_origins: str = "*"

    # ── Serverless Detection ─────────────────────────────────
    is_serverless: bool = Field(default_factory=lambda: bool(os.environ.get("VERCEL")))

    # ── Computed ──────────────────────────────────────────────

    @field_validator("rate_limit_per_minute", mode="before")
    @classmethod
    def parse_rate_limit(cls, v: object) -> int:
        if v is None or v == "":
            return 60
        return int(v)

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if v is None or v == "":
            return False
        if isinstance(v, str):
            return v.lower() in ("true", "1", "t", "yes")
        return bool(v)

    @field_validator("log_level", mode="before")
    @classmethod
    def parse_log_level(cls, v: object) -> str:
        if not v or str(v).upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            return "INFO"
        return str(v).upper()

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> str:
        if not v:
            return "*"
        return str(v)

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str, info: object) -> str:
        if v:
            url = str(v).strip()
            if url.startswith("sqlite"):
                if os.environ.get("VERCEL"):
                    return "sqlite+aiosqlite:////tmp/omnicart.db"
                return url
            # Standardize postgres prefix for asyncpg (e.g. from Neon / Supabase / Heroku)
            if url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            return url

        data: dict[str, object] = getattr(info, "data", {})
        user = data.get("postgres_user", "omnicart")
        password = data.get("postgres_password", "")
        host = data.get("postgres_host", "postgres")
        port = data.get("postgres_port", 5432)
        db = data.get("postgres_db", "omnicart_db")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def telegram_bot_token_secret_key(self) -> bytes:
        """HMAC key derived from bot token for Telegram initData validation (WebAppData)."""
        return hmac.new(
            key=b"WebAppData",
            msg=self.telegram_bot_token.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton cached settings instance."""
    return Settings()  # type: ignore[call-arg]
