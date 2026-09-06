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
    telegram_bot_token: str = Field(..., min_length=20)
    telegram_webapp_url: str = Field(..., min_length=8)
    telegram_webhook_secret: str = ""

    # ── Database ──────────────────────────────────────────────
    postgres_user: str = "omnicart"
    postgres_password: str = ""
    postgres_db: str = "omnicart_db"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: str = ""

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── B.AI API ──────────────────────────────────────────────
    bai_api_key: str = Field(..., min_length=3)
    bai_api_base: str = "https://api.b.ai/v1"
    bai_model: str = "gpt-4o"

    # ── Security ──────────────────────────────────────────────
    secret_key: str = Field(..., min_length=32)
    rate_limit_per_minute: int = 60
    cron_secret: str = ""

    # ── App ───────────────────────────────────────────────────
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    allowed_origins: str = "*"

    # ── Serverless Detection ─────────────────────────────────
    is_serverless: bool = Field(default_factory=lambda: bool(os.environ.get("VERCEL")))

    # ── Computed ──────────────────────────────────────────────

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str, info: object) -> str:
        if v:
            url = v.strip()
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
