import atexit
import sys
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Store the provider for explicit shutdown via atexit
_provider: TracerProvider | None = None


def _flush_on_exit() -> None:
    """Force-flush remaining spans before stdout is closed during shutdown.

    ``ConsoleSpanExporter`` writes to ``sys.stdout`` behind the scenes.
    Python's shutdown order is nondeterministic, so the SDK's background
    exporter thread may try to write *after* the interpreter has already
    closed stdout.  ``SimpleSpanProcessor`` avoids the background thread
    (no batch timer), and this ``atexit`` hook guarantees a final flush
    before the C runtime tears down file descriptors.
    """
    global _provider
    if _provider is not None:
        try:
            _provider.force_flush(timeout_millis=1_000)
        except Exception:
            pass  # Silently ignore — we're shutting down anyway.


def setup_telemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry for tracing.

    Uses ``SimpleSpanProcessor`` (synchronous, no background thread)
    and an ``atexit`` flush hook to avoid the common shutdown race
    where ``ConsoleSpanExporter`` tries to write to already-closed
    ``sys.stdout``.  Replacement with an OTLP exporter is recommended
    for production deployments.
    """
    global _provider

    # Initialize Tracer Provider
    provider = TracerProvider()

    # Export to console for local dev (Production would use Jaeger/OTLP)
    # SimpleSpanProcessor is used instead of BatchSpanProcessor to avoid
    # background-thread races during interpreter shutdown.
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    _provider = provider

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Register atexit hook to flush before stdout is closed
    atexit.register(_flush_on_exit)

    logger.info("OpenTelemetry instrumentation complete")


def get_tracer(name: str):
    """Get a tracer instance."""
    return trace.get_tracer(name)
