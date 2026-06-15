"""
Audit Middleware (Phase 6).

Logs all HTTP requests to the audit log for security monitoring and compliance.
Tracks request method, path, status code, user (if authenticated), IP, and timing.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.logging import get_logger
from backend.core.audit import log_api_request

logger = get_logger(__name__)

# Paths to exclude from audit logging (health checks, static assets)
EXCLUDED_PATHS = {"/health", "/", "/favicon.ico"}
EXCLUDED_PREFIXES = ("/docs", "/openapi", "/redoc")


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs API requests for security auditing."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip excluded paths
        if path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PREFIXES):
            return await call_next(request)

        # Skip preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        start_time = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"

        # Try to extract user UUID from JWT
        user_uuid: Optional[str] = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from backend.core.security import decode_access_token
                payload = decode_access_token(token)
                user_uuid = payload.get("user_uuid")
            except Exception:
                pass

        # Process request
        response = await call_next(request)

        elapsed = time.monotonic() - start_time

        log_api_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            client_ip=client_ip,
            user_uuid=user_uuid,
            duration_ms=round(elapsed * 1000, 2),
        )

        return response