"""
OmniCart AI — Telegram Bot Webhook Serverless Entry Point.
Dispatches incoming Telegram update payloads to aiogram.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

for p in [str(BACKEND_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from api.main import app  # noqa: E402

__all__ = ["app"]
