"""Unit tests for Rate Limiting & Concurrency (Phase 6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, Response


# Patch Redis connection at module level so RateLimitMiddleware.__init__
# doesn't actually try to connect to a real Redis server.
@pytest.fixture(autouse=True)
def _patch_redis_connect():
    with patch("backend.api.middleware.rate_limit.redis_module.Redis") as mock_redis:
        mock_instance = MagicMock()
        mock_instance.ping.return_value = True
        mock_redis.return_value = mock_instance
        yield


class TestRateLimitMiddleware:
    def test_middleware_class_exists(self):
        from backend.api.middleware.rate_limit import RateLimitMiddleware
        assert RateLimitMiddleware is not None

    @pytest.mark.asyncio
    async def test_middleware_allows_request(self):
        from backend.api.middleware.rate_limit import RateLimitMiddleware

        mock_app = AsyncMock()
        middleware = RateLimitMiddleware(mock_app)
        # Simulate Redis unavailable but fail-open
        import backend.api.middleware.rate_limit as rl_mod
        rl_mod.settings.RATE_LIMIT_FAIL_CLOSED = False
        middleware._redis = None
        middleware._redis_available = False

        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.url.path = "/api/query"
        mock_request.method = "GET"
        mock_request.headers = {}

        mock_call_next = AsyncMock(return_value=Response("OK", status_code=200))

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_skips_options(self):
        from backend.api.middleware.rate_limit import RateLimitMiddleware

        mock_app = AsyncMock()
        middleware = RateLimitMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "OPTIONS"
        mock_request.url.path = "/api/query"
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"

        mock_call_next = AsyncMock(return_value=Response("OK", status_code=200))

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200


class TestConcurrencyMiddleware:
    def test_concurrency_middleware_exists(self):
        try:
            from backend.api.middleware.concurrency import ConcurrencyControlMiddleware
            assert ConcurrencyControlMiddleware is not None
        except ImportError:
            pytest.skip("ConcurrencyControlMiddleware not available")

    @pytest.mark.asyncio
    async def test_concurrency_allows_request(self):
        try:
            from backend.api.middleware.concurrency import ConcurrencyControlMiddleware
        except ImportError:
            pytest.skip("ConcurrencyControlMiddleware not available")

        mock_app = AsyncMock()
        middleware = ConcurrencyControlMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/query"
        mock_request.method = "GET"

        mock_call_next = AsyncMock(return_value=Response("OK", status_code=200))

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200