"""
OmniCart AI — Vercel Serverless Function Entry Point.
Exports the FastAPI application for Vercel's Python ASGI runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add the 'backend' directory to sys.path so existing module imports work seamlessly
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

for p in [str(BACKEND_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import the configured FastAPI app from backend.api.main
from api.main import app  # noqa: E402

# Export 'app' for Vercel Python runtime
__all__ = ["app"]
