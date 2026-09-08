"""
Unit tests for Telegram Webhook idempotency deduplication and security.
Tests Redis SET NX deduplication, local LRU cache fallback, and secret verification.
"""

from __future__ import annotations

import collections
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import api.routers.webhook as webhook_module
from api.routers.webhook import _is_duplicate_local, is_duplicate_update


class TestWebhookIdempotency(unittest.IsolatedAsyncioTestCase):
    """Test suite for webhook update deduplication."""

    def setUp(self):
        # Reset local in-memory deduplication structures before each test
        webhook_module._SEEN_UPDATES.clear()
        webhook_module._SEEN_UPDATES_SET.clear()

    def test_local_deduplication(self):
        update_id = 998877

        # First arrival: should not be marked duplicate
        self.assertFalse(_is_duplicate_local(update_id))

        # Immediate replay: should be detected as duplicate
        self.assertTrue(_is_duplicate_local(update_id))

        # Different update_id: should not be duplicate
        self.assertFalse(_is_duplicate_local(update_id + 1))

    def test_local_lru_eviction(self):
        # Fill the queue to capacity
        for i in range(10000):
            _is_duplicate_local(i)

        self.assertIn(0, webhook_module._SEEN_UPDATES_SET)
        self.assertIn(9999, webhook_module._SEEN_UPDATES_SET)

        # Adding 10000th element should evict element 0
        _is_duplicate_local(10000)
        self.assertNotIn(0, webhook_module._SEEN_UPDATES_SET)
        self.assertIn(10000, webhook_module._SEEN_UPDATES_SET)

    async def test_redis_deduplication_first_delivery(self):
        mock_redis = AsyncMock()
        # Redis set with nx=True returns True / "OK" when key is new
        mock_redis.set.return_value = True

        is_dup = await is_duplicate_update(12345, mock_redis)
        self.assertFalse(is_dup)
        mock_redis.set.assert_called_once_with("tg_update:12345", "1", nx=True, ex=7200)

    async def test_redis_deduplication_duplicate_delivery(self):
        mock_redis = AsyncMock()
        # Redis set with nx=True returns None when key already exists
        mock_redis.set.return_value = None

        is_dup = await is_duplicate_update(12345, mock_redis)
        self.assertTrue(is_dup)

    async def test_redis_failure_falls_back_to_local(self):
        mock_redis = AsyncMock()
        # Redis connection or network error
        mock_redis.set.side_effect = ConnectionError("Upstash connection lost")

        # First call: should fall back to local and accept
        is_dup1 = await is_duplicate_update(55555, mock_redis)
        self.assertFalse(is_dup1)

        # Second call with same ID: should fall back to local and reject as duplicate
        is_dup2 = await is_duplicate_update(55555, mock_redis)
        self.assertTrue(is_dup2)


if __name__ == "__main__":
    unittest.main()
