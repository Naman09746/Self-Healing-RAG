"""Request ID middleware for OpenTelemetry correlation.

Extracts the ``x-request-id`` header from incoming HTTP requests and injects it
into OTel baggage, creating a root span tagging the entire request trace.
"""

from __future__ import annotations

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace
from backend.core.observability import set_request_id, get_tracer
from backend.core.logging import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures every request has a ``request_id``.

    1. Reads ``x-request-id`` from headers, or generates one.
    2. Injects it into OTel baggage for downstream span correlation.
    3. Creates a root ``rag_request`` span for the entire HTTP request.
    4. Sets the ``x-request-id`` response header for client-side tracing.
    """

    async def dispatch(self, request: Request, call_next):
        # 1. Resolve request ID
        request_id = request.headers.get("x-request-id")
        if not request_id:
            request_id = str(uuid.uuid4())

        # 2. Inject into OTel baggage
        set_request_id(request_id)

        # 3. Start root span
        tracer = get_tracer()
        with tracer.start_as_current_span("rag_request") as span:
            span.set_attribute("request_id", request_id)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.host", request.url.hostname)

            # 4. Process request
            response = await call_next(request)

            # 5. Tag response
            span.set_attribute("http.status_code", response.status_code)
            response.headers["x-request-id"] = request_id

        return response