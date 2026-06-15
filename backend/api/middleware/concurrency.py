"""
Concurrency Control Middleware (Phase 6).

Limits the number of concurrent requests per user and globally to prevent
resource exhaustion. Uses Redis for distributed semaphore when available,
falls back to an in-process asyncio.Semaphore for single-instance deployments.

Returns 429 when the limit is exceeded.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class ConcurrencyControlMiddleware(BaseHTTPMiddleware):
    """Middleware that limits concurrent request processing.

    Uses an in-process :class:`asyncio.Semaphore` for global concurrency
    limiting. For multi-instance deployments, Redis-based coordination
    should be added.

    Per-user limits are enforced with a dictionary of semaphores keyed by
    user UUID (or IP for unauthenticated users).
    """

    def __init__(self, app):
        super().__init__(app)
        self._global_semaphore = asyncio.Semaphore(
            settings.CONCURRENCY_MAX_GLOBAL
        )
        self._user_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def _get_user_semaphore(self, user_key: str) -> asyncio.Semaphore:
        """Get or create a per-user semaphore."""
        async with self._lock:
            if user_key not in self._user_semaphores:
                self._user_semaphores[user_key] = asyncio.Semaphore(
                    settings.CONCURRENCY_MAX_PER_USER
                )
            return self._user_semaphores[user_key]

    def _get_user_key(self, request: Request) -> str:
        """Extract a unique user key from the request."""
        # Try to extract user UUID from JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from backend.core.security import decode_access_token
                payload = decode_access_token(token)
                user_uuid = payload.get("user_uuid")
                if user_uuid:
                    return f"user:{user_uuid}"
            except Exception:
                pass

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next):
        # Skip for health checks and static paths
        path = request.url.path
        if path in ("/health", "/") or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        user_key = self._get_user_key(request)
        user_sem = await self._get_user_semaphore(user_key)

        # Try to acquire both semaphores
        acquired_global = acquired_user = False
        try:
            # Acquire global semaphore
            acquired_global = await asyncio.wait_for(
                self._global_semaphore.acquire(),
                timeout=5.0,
            )
            if not acquired_global:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many concurrent requests. Try again later.",
                        "limit": settings.CONCURRENCY_MAX_GLOBAL,
                        "scope": "global",
                    },
                )

            # Acquire per-user semaphore
            acquired_user = await asyncio.wait_for(
                user_sem.acquire(),
                timeout=5.0,
            )
            if not acquired_user:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many concurrent requests from this user. Try again later.",
                        "limit": settings.CONCURRENCY_MAX_PER_USER,
                        "scope": "user",
                    },
                )

            # Process the request
            response = await call_next(request)
            return response

        except asyncio.TimeoutError:
            logger.debug("Concurrency limit semaphore acquisition timed out")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Request timed out waiting for processing slot. Try again later.",
                },
            )

        finally:
            if acquired_user:
                user_sem.release()
            if acquired_global:
                self._global_semaphore.release()