"""
Observability infrastructure for Phase 4C.

Provides a unified OpenTelemetry + LangSmith setup for distributed tracing
across all RAG pipeline components.

Architecture
------------
+------------------+--------------------------------------------------+
| Layer            | Details                                          |
+==================+==================================================+
| OpenTelemetry    | Root tracer for infra-level spans (retrieval,    |
|                  | reranking, critic, cache, generation)            |
+------------------+--------------------------------------------------+
| LangSmith        | Run tree for LLM-level observability (token      |
|                  | counts, prompt templates, model params)          |
+------------------+--------------------------------------------------+
| Request ID       | ``x-request-id`` header propagated via OTel      |
|                  | baggage, correlated across all spans             |
+------------------+--------------------------------------------------+

Trace Hierarchy
---------------
rag_request                                       (root span)
├── cache.check                                   (check semantic cache)
├── cache.store                                   (store in semantic cache)
├── retrieval                                     (hybrid retrieval)
│   ├── vector_search                             (ChromaDB query)
│   ├── bm25_search                               (BM25 sparse retrieval)
│   ├── graph_search                              (Neo4j traversal)
│   └── rrf_fusion                                (reciprocal rank fusion)
├── reranking                                     (cross-encoder rerank)
├── generation                                    (LLM generation)
│   └── llm.generate                             (Ollama LLM call)
├── critic                                        (grounding verification)
│   ├── claim_extraction                          (extract claims from answer)
│   └── claim_verification                        (verify each claim)
│       └── llm.verify_claim                      (per-claim LLM call)
├── healing.query_rewrite                         (query rewriting)
└── evaluation                                    (evaluation metrics)

Usage
-----
.. code-block:: python

    from backend.core.observability import tracer, langsmith_run

    with tracer.start_as_current_span("my_span") as span:
        span.set_attribute("key", "value")
        with langsmith_run("llm_call", inputs={"prompt": prompt}) as run:
            result = llm.generate(prompt)
            run.end(outputs={"result": result})
"""

from __future__ import annotations

import os
import sys
import atexit
from typing import Any, Optional
from contextlib import contextmanager
from opentelemetry import trace, baggage
from opentelemetry.sdk.trace import TracerProvider, Tracer
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.trace import Span, Status, StatusCode, NonRecordingSpan

from langsmith import Client as LangSmithClient
from langsmith.run_trees import RunTree

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_tracer: Tracer | None = None
_provider: TracerProvider | None = None
_langsmith_client: LangSmithClient | None = None


# ---------------------------------------------------------------------------
# OpenTelemetry setup
# ---------------------------------------------------------------------------


def setup_otel_tracing(
    service_name: str = "self-healing-rag",
    otlp_endpoint: str | None = None,
    use_console: bool = False,
) -> Tracer:
    """Configure the OpenTelemetry ``TracerProvider`` and return a tracer.

    Args:
        service_name: Resource name for the service.
        otlp_endpoint: OTLP HTTP endpoint for exporting traces.
                       Example: ``http://localhost:4318/v1/traces``.
        use_console: If ``True``, also export to console (useful for dev).

    Returns:
        A :class:`Tracer` instance named after ``service_name``.
    """
    global _tracer, _provider

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # ---- Exporters ----

    # OTLP HTTP exporter (primary)
    endpoint = otlp_endpoint or settings.OTEL_EXPORTER_OTLP_ENDPOINT
    if endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Console exporter for local development
    if use_console or settings.OTEL_CONSOLE_EXPORT:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    # Fallback: if no exporter configured, at least export to console
    if not endpoint and not use_console and not settings.OTEL_CONSOLE_EXPORT:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.warning("No OTLP endpoint configured. Falling back to console export.")

    trace.set_tracer_provider(provider)
    _provider = provider

    tracer = provider.get_tracer(service_name)
    _tracer = tracer

    # Register atexit hook to flush before interpreter shutdown
    atexit.register(_flush_traces)

    logger.info(
        "OpenTelemetry tracing configured",
        otlp_endpoint=endpoint or "console",
        service_name=service_name,
    )
    return tracer


def _flush_traces() -> None:
    """Force-flush remaining spans at exit."""
    global _provider
    if _provider is not None:
        try:
            _provider.force_flush(timeout_millis=2_000)
        except Exception:
            pass


def get_tracer() -> Tracer:
    """Return the global tracer instance.

    Raises:
        RuntimeError: If ``setup_otel_tracing()`` has not been called.
    """
    if _tracer is None:
        raise RuntimeError(
            "OpenTelemetry tracer not initialized. "
            "Call setup_otel_tracing() before get_tracer()."
        )
    return _tracer


# ---------------------------------------------------------------------------
# LangSmith setup
# ---------------------------------------------------------------------------


def setup_langsmith(
    api_key: str | None = None,
    project_name: str | None = None,
) -> LangSmithClient:
    """Configure and return a LangSmith client.

    Args:
        api_key: LangSmith API key. Falls back to ``LANGSMITH_API_KEY`` env var.
        project_name: LangSmith project name. Falls back to ``LANGSMITH_PROJECT``.

    Returns:
        A :class:`langsmith.Client` instance.
    """
    global _langsmith_client

    key = api_key or settings.LANGSMITH_API_KEY or os.environ.get("LANGSMITH_API_KEY")
    project = project_name or settings.LANGSMITH_PROJECT or "self-healing-rag"

    if not key:
        logger.warning(
            "LangSmith API key not configured. "
            "Set LANGSMITH_API_KEY in .env or environment. "
            "LangSmith tracing will be disabled."
        )
        _langsmith_client = None
        return None  # type: ignore[return-value]

    client = LangSmithClient(api_key=key)
    _langsmith_client = client

    logger.info("LangSmith client configured", project=project)
    return client


def get_langsmith_client() -> LangSmithClient | None:
    """Return the global LangSmith client, or ``None`` if not configured."""
    return _langsmith_client


# ---------------------------------------------------------------------------
# Request ID correlation via OTel baggage
# ---------------------------------------------------------------------------


def set_request_id(request_id: str) -> None:
    """Inject ``request_id`` into OTel baggage for downstream correlation."""
    ctx = baggage.set_baggage("request_id", request_id)
    trace.set_span_in_context(trace.get_current_span(), ctx)


def get_request_id() -> str | None:
    """Read ``request_id`` from OTel baggage."""
    return baggage.get_baggage("request_id")


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


@contextmanager
def span_with_status(name: str, **attributes: Any):
    """Start a span, set attributes, and auto-record OK/error status.

    Usage::

        with span_with_status("my_span", key="value") as span:
            result = do_work()
            span.set_attribute("result_length", len(result))
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        for k, v in attributes.items():
            span.set_attribute(k, str(v) if not isinstance(v, (int, float)) else v)
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span (if one exists)."""
    span = trace.get_current_span()
    if span and not isinstance(span, NonRecordingSpan):
        span.add_event(name, attributes or {})


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


async def shutdown_observability() -> None:
    """Flush all pending spans and close exporters.

    Call during application shutdown.
    """
    global _provider
    if _provider is not None:
        _provider.force_flush(timeout_millis=5_000)
        _provider.shutdown()
        logger.info("OpenTelemetry provider shut down")