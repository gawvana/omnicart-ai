"""
OmniCart AI — Telegram Bot Webhook Management Script.
Use this script to configure or remove the Telegram bot webhook for Vercel hosting.

Usage:
  python -m bot.set_webhook set https://your-project.vercel.app
  python -m bot.set_webhook get
  python -m bot.set_webhook delete
"""

from __future__ import annotations

import asyncio
import sys

from aiogram import Bot
from core.config import get_settings


async def main() -> None:
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)

    action = sys.argv[1] if len(sys.argv) > 1 else "get"

    try:
        if action == "set":
            base_url = sys.argv[2] if len(sys.argv) > 2 else settings.telegram_webapp_url
            webhook_url = f"{base_url.rstrip('/')}/api/webhook"
            secret = settings.telegram_webhook_secret or None

            print(f"Setting webhook to: {webhook_url}")
            await bot.set_webhook(
                url=webhook_url,
                secret_token=secret,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
            )
            print("Webhook set successfully!")

        elif action == "delete":
            print("Deleting webhook...")
            await bot.delete_webhook(drop_pending_updates=True)
            print("Webhook deleted successfully!")

        elif action == "get":
            info = await bot.get_webhook_info()
            print("Current Webhook Info:")
            print(f"  URL: {info.url}")
            print(f"  Has custom cert: {info.has_custom_certificate}")
            print(f"  Pending update count: {info.pending_update_count}")
            print(f"  Last error date: {info.last_error_date}")
            print(f"  Last error message: {info.last_error_message}")
            print(f"  Max connections: {info.max_connections}")
        else:
            print(f"Unknown action: {action}. Available: set, get, delete")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
