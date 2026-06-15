"""
Prometheus Metrics — Self-Healing RAG Pipeline.

Provides application-level metrics for Prometheus scraping, covering:
- HTTP request rate, latency, and status codes
- RAG pipeline throughput (queries, healing cycles, cache hits)
- RAG quality metrics (grounding score, hallucination rate, verdict distribution)
- Infrastructure health (active requests, queue depth)

Usage:
    from backend.core.metrics import metrics
    metrics.rag_queries_total.inc()
    metrics.rag_grounding_score.set(0.92)
"""

from __future__ import annotations

import time
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class MetricsRegistry:
    """Central registry for all Self-Healing RAG Prometheus metrics."""

    def __init__(self) -> None:
        # ── HTTP Metrics ──────────────────────────────────────
        self.http_requests_total: Counter = Counter(
            "http_requests_total",
            "Total HTTP requests by method, path, and status",
            ["method", "path", "status"],
        )
        self.http_request_duration_seconds: Histogram = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds by method and path",
            ["method", "path"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
        )
        self.http_requests_in_progress: Gauge = Gauge(
            "http_requests_in_progress",
            "Number of HTTP requests currently in progress",
            ["method"],
        )

        # ── RAG Pipeline Metrics ──────────────────────────────
        self.rag_queries_total: Counter = Counter(
            "rag_queries_total",
            "Total RAG queries processed",
        )
        self.rag_queries_in_progress: Gauge = Gauge(
            "rag_queries_in_progress",
            "Number of RAG queries currently being processed",
        )
        self.rag_query_duration_seconds: Histogram = Histogram(
            "rag_query_duration_seconds",
            "End-to-end RAG query duration in seconds",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
        )
        self.rag_query_timeouts_total: Counter = Counter(
            "rag_query_timeouts_total",
            "Total number of RAG query timeouts",
        )

        # ── Cache Metrics ─────────────────────────────────────
        self.rag_cache_hits_total: Counter = Counter(
            "rag_cache_hits_total",
            "Total semantic cache hits",
        )
        self.rag_cache_misses_total: Counter = Counter(
            "rag_cache_misses_total",
            "Total semantic cache misses",
        )

        # ── Hallucination & Healing Metrics ────────────────────
        self.rag_hallucinations_total: Counter = Counter(
            "rag_hallucinations_total",
            "Total hallucination events detected",
        )
        self.rag_healings_total: Counter = Counter(
            "rag_healings_total",
            "Total healing cycles triggered by outcome",
            ["outcome"],
        )
        self.rag_grounding_score: Gauge = Gauge(
            "rag_grounding_score",
            "Current grounding score (0.0 – 1.0)",
        )
        self.rag_faithfulness_score: Gauge = Gauge(
            "rag_faithfulness_score",
            "RAGAS faithfulness score (0.0 – 1.0)",
        )
        self.rag_answer_relevancy: Gauge = Gauge(
            "rag_answer_relevancy",
            "RAGAS answer relevancy score (0.0 – 1.0)",
        )
        self.rag_context_precision: Gauge = Gauge(
            "rag_context_precision",
            "RAGAS context precision score (0.0 – 1.0)",
        )

        # ── Verdict Distribution ───────────────────────────────
        self.rag_verdicts_total: Counter = Counter(
            "rag_verdicts_total",
            "Total critic verdicts by type",
            ["verdict"],
        )

        # ── Security Metrics ──────────────────────────────────
        self.rag_auth_attempts_total: Counter = Counter(
            "rag_auth_attempts_total",
            "Total authentication attempts by result",
            ["result"],
        )
        self.rag_prompt_injection_blocked_total: Counter = Counter(
            "rag_prompt_injection_blocked_total",
            "Total prompt injection attempts blocked",
        )

        # ── Document / Ingestion Metrics ──────────────────────
        self.rag_documents_ingested_total: Counter = Counter(
            "rag_documents_ingested_total",
            "Total documents ingested by type",
            ["document_type"],
        )
        self.rag_chunks_indexed_total: Counter = Counter(
            "rag_chunks_indexed_total",
            "Total chunks indexed",
        )

        # ── LLM Metrics ───────────────────────────────────────
        self.rag_llm_calls_total: Counter = Counter(
            "rag_llm_calls_total",
            "Total LLM calls by model and phase",
            ["model", "phase"],
        )
        self.rag_llm_tokens_total: Counter = Counter(
            "rag_llm_tokens_total",
            "Total LLM tokens used by model and type",
            ["model", "type"],  # type = prompt / completion / total
        )
        self.rag_llm_call_duration_seconds: Histogram = Histogram(
            "rag_llm_call_duration_seconds",
            "LLM call latency in seconds by model and phase",
            ["model", "phase"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )

    # ── Convenience Methods ──────────────────────────────────

    def inc_query(self) -> None:
        self.rag_queries_total.inc()

    def inc_hallucination(self) -> None:
        self.rag_hallucinations_total.inc()

    def inc_healing(self, outcome: str = "triggered") -> None:
        self.rag_healings_total.labels(outcome=outcome).inc()

    def set_grounding_score(self, score: float) -> None:
        self.rag_grounding_score.set(score)

    def inc_verdict(self, verdict: str) -> None:
        self.rag_verdicts_total.labels(verdict=verdict).inc()

    def inc_cache_hit(self) -> None:
        self.rag_cache_hits_total.inc()

    def inc_cache_miss(self) -> None:
        self.rag_cache_misses_total.inc()

    def inc_auth_attempt(self, result: str = "success") -> None:
        self.rag_auth_attempts_total.labels(result=result).inc()

    def inc_prompt_injection_blocked(self) -> None:
        self.rag_prompt_injection_blocked_total.inc()

    def track_llm_call(
        self,
        model: str = "mistral:7b",
        phase: str = "generation",
        duration_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self.rag_llm_calls_total.labels(model=model, phase=phase).inc()
        self.rag_llm_tokens_total.labels(model=model, type="prompt").inc(prompt_tokens)
        self.rag_llm_tokens_total.labels(model=model, type="completion").inc(completion_tokens)
        self.rag_llm_tokens_total.labels(model=model, type="total").inc(prompt_tokens + completion_tokens)
        self.rag_llm_call_duration_seconds.labels(model=model, phase=phase).observe(duration_ms / 1000.0)


# Global metrics singleton
metrics = MetricsRegistry()


class PrometheusMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that records HTTP metrics for Prometheus.

    Tracks:
    - Request count by method, path, and status code
    - Request latency histogram by method and path
    - In-progress request gauge by method
    """

    EXCLUDED_PATHS = {"/metrics", "/health", "/favicon.ico"}
    EXCLUDED_PREFIXES = ("/docs", "/openapi", "/redoc")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip excluded paths
        if path in self.EXCLUDED_PATHS or path.startswith(self.EXCLUDED_PREFIXES):
            return await call_next(request)

        method = request.method
        metrics.http_requests_in_progress.labels(method=method).inc()
        start_time = time.monotonic()

        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        except Exception as exc:
            status = "500"
            raise
        finally:
            duration = time.monotonic() - start_time
            metrics.http_requests_total.labels(method=method, path=path, status=status).inc()
            metrics.http_request_duration_seconds.labels(method=method, path=path).observe(duration)
            metrics.http_requests_in_progress.labels(method=method).dec()


async def metrics_endpoint(request: Request) -> Response:
    """Serve Prometheus metrics at ``GET /metrics``.

    Usage in FastAPI::

        from backend.core.metrics import metrics_endpoint

        app.add_route("/metrics", metrics_endpoint)
    """
    return Response(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
