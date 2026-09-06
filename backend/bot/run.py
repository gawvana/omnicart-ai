"""
OmniCart AI — Bot runner (polling mode).
Registers all routers, sets up middleware for DB session injection, and starts polling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Dispatcher
from aiogram import BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.handlers.start import router as start_router
from core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Injects `db_session` into handler kwargs for every update."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["db_session"] = session
            return await handler(event, data)


async def main() -> None:
    settings = get_settings()

    engine_kwargs: dict[str, Any] = {
        "echo": settings.debug,
    }
    if "sqlite" not in settings.database_url:
        engine_kwargs.update({
            "pool_size": 10,
            "max_overflow": 5,
            "pool_pre_ping": True,
        })
    engine = create_async_engine(settings.database_url, **engine_kwargs)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables on startup
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Register middleware
    dp.update.outer_middleware(DatabaseMiddleware(session_factory))

    # Register routers
    dp.include_router(start_router)

    logger.info("Starting OmniCart AI bot polling...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await engine.dispose()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
