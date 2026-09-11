"""
Rate Limiting Middleware — hardened Redis-backed rate limiter (Phase 6).

Features:
  - Redis authentication via REDIS_PASSWORD setting
  - Optional Redis TLS via REDIS_USE_SSL setting
  - User-based + IP-based rate limiting
  - Fail-closed behavior: returns 503 when Redis is unavailable
  - Stricter limits for auth endpoints
  - Audit logging for rate limit hits
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis as redis_module

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.audit import log_rate_limit_hit

logger = get_logger(__name__)

# Auth endpoints get stricter limits
AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/signup"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed rate limiter.

    Limits requests per IP (and per user ID if available) within a rolling
    time window. If Redis is down and ``RATE_LIMIT_FAIL_CLOSED`` is True,
    all requests are rejected with 503.
    """

    def __init__(self, app):
        super().__init__(app)
        self._redis: Optional[redis_module.Redis] = None
        self._redis_available = False
        self._try_connect()

    def _try_connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            if getattr(settings, "REDIS_URL", None):
                self._redis = redis_module.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
            else:
                self._redis = redis_module.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    ssl=settings.REDIS_USE_SSL,
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
            self._redis.ping()
            self._redis_available = True
            logger.info("Rate limiter connected to Redis")
        except Exception as e:
            self._redis_available = False
            self._redis = None
            logger.warning(
                "Rate limiter could not connect to Redis",
                error=str(e),
                fail_closed=settings.RATE_LIMIT_FAIL_CLOSED,
            )

    def _get_limit(self, path: str) -> int:
        """Return the rate limit for the given request path."""
        if path in AUTH_PATHS:
            return settings.RATE_LIMIT_AUTH
        return settings.RATE_LIMIT_DEFAULT

    async def dispatch(self, request: Request, call_next):
        # Skip preflight requests, health checks, metrics, and docs
        if request.method == "OPTIONS" or request.url.path in {
            "/health",
            "/api/v1/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
        }:
            return await call_next(request)

        # Determine limit for this endpoint
        limit = self._get_limit(request.url.path)
        window = settings.RATE_LIMIT_WINDOW

        # Key by user ID (if available) + IP address
        client_ip = request.client.host if request.client else "unknown"

        # Try to extract user UUID from JWT (if authenticated) — use cached decode + request.state
        user_uuid: Optional[str] = None
        # Check if already decoded by earlier middleware (stored in request.state)
        if hasattr(request.state, "user_uuid") and getattr(request.state, "user_uuid"):
            user_uuid = request.state.user_uuid
        else:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    from backend.core.security import cached_decode_access_token
                    payload = cached_decode_access_token(token)
                    user_uuid = payload.get("user_uuid")
                    # Cache in request.state for downstream middlewares
                    request.state.user_uuid = user_uuid
                    request.state.jwt_payload = payload
                except Exception:
                    pass  # Token invalid or expired — rate limit by IP only

        if user_uuid:
            key = f"rate_limit:{user_uuid}"
        else:
            key = f"rate_limit:{client_ip}"

        # ---- Check rate limit — atomic INCR + EXPIRE (no race) ----
        if self._redis_available:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, window)
                results = pipe.execute()
                current = int(results[0]) if results and results[0] is not None else 1
                if current > limit:
                    logger.warning(
                        "Rate limit exceeded",
                        ip=client_ip,
                        user_uuid=user_uuid,
                        limit=limit,
                        current=current,
                    )
                    log_rate_limit_hit(
                        ip_address=client_ip,
                        user_uuid=user_uuid,
                        endpoint=request.url.path,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded. Try again later.",
                            "limit": limit,
                            "window_seconds": window,
                        },
                    )
            except Exception as e:
                logger.debug("Rate limit Redis error", error=str(e))
                # Fall through to fail-closed logic below
                if settings.RATE_LIMIT_FAIL_CLOSED:
                    return JSONResponse(
                        status_code=503,
                        content={
                            "detail": "Service temporarily unavailable (rate limiter unavailable)."
                        },
                    )
        else:
            # Redis is not available
            if settings.RATE_LIMIT_FAIL_CLOSED:
                logger.debug("Rate limiting fail-closed: rejecting request")
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": "Service temporarily unavailable (rate limiter unavailable)."
                    },
                )
            # Fail-open: allow request
            logger.debug("Rate limiting fail-open: allowing request")

        response = await call_next(request)
        return response