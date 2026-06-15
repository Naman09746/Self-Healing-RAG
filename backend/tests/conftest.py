import pytest
from backend.core.observability import setup_otel_tracing

@pytest.fixture(scope="session", autouse=True)
def setup_test_tracing():
    """Session-scoped autouse fixture to initialize tracing for tests."""
    setup_otel_tracing(
        service_name="test-self-healing-rag",
        otlp_endpoint=None,  # Do not export to a real collector in tests
        use_console=False,   # Keep test output clean
    )
