"""
Integration test for the SSE streaming endpoint (``POST /api/v1/query/stream``).

Validates that:
- The endpoint returns ``text/event-stream`` on a successful request
- Phase events are emitted in the correct order
- Token events contain decoded tokens
- The final metadata event includes the answer and chunk count

The test overrides the auth dependency and injects controlled doubles
for the graph and service container so no external infrastructure
(Ollama, Chroma, Postgres) is required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, AsyncMock
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers.auth import get_current_user
from backend.storage.db.models import User as DBUser


# ---------------------------------------------------------------------------
# Dummy user — returned from the overridden auth dependency
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_user() -> DBUser:
    user = MagicMock(spec=DBUser)
    user.user_uuid = "test-uuid-0000"
    user.tenant_id = "test-tenant"
    return user


# ---------------------------------------------------------------------------
# Dummy graph and deps — injected into app.state
# ---------------------------------------------------------------------------

class _DummyGraph:
    """Minimal LangGraph stub as used by the unit tests."""

    async def astream(self, state, stream_mode="values"):
        phases = ["intake", "planning", "retrieval", "generation", "critic", "completed"]
        chunks = [{"content": "ctx", "score": 0.9}]
        for phase in phases:
            step = {
                "query": state.query,
                "session_id": state.session_id,
                "current_phase": phase,
                "retry_count": 0,
                "retrieved_chunks": chunks if phase not in ("intake", "planning") else [],
                "generation_result": {"answer": "Hello world!"},
            }
            if phase == "generation" and state._token_queue is not None:
                for token in ["Hello", " ", "world", "!"]:
                    await state._token_queue.put(token)
            yield step


class _DummyDeps:
    def __init__(self):
        self.query_cache = MagicMock()
        self.query_cache.get_cached_query.return_value = None


# ---------------------------------------------------------------------------
# App fixture with overridden deps
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app(dummy_user: DBUser) -> FastAPI:
    """Return a FastAPI app with overridden auth and dummy graph/deps."""

    def _override_get_current_user():
        return dummy_user

    app.dependency_overrides[get_current_user] = _override_get_current_user

    # Inject dummy services — we don't need the real ones for this test.
    app.state.rag_graph = _DummyGraph()
    app.state.svc = _DummyDeps()

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStreamEndpoint:
    """Integration tests for the ``POST /v1/query/stream`` SSE endpoint."""

    def _parse_sse(self, text: str) -> list[dict]:
        """Convert raw SSE response body to a list of ``{event, data}`` dicts."""
        parsed = []
        for frame in text.strip().split("\n\n"):
            if not frame.strip():
                continue
            lines = frame.strip().split("\n")
            evt = ""
            data = {}
            for line in lines:
                if line.startswith("event: "):
                    evt = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
            parsed.append({"event": evt, "data": data})
        return parsed

    def test_returns_event_stream_content_type(self, client: TestClient):
        """The response should have ``text/event-stream`` media type."""
        resp = client.post(
            "/api/v1/query/stream",
            json={"query": "hello", "session_id": "sess_1"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

    def test_emits_phase_events_in_order(self, client: TestClient):
        """Phase events should appear in pipeline order."""
        resp = client.post(
            "/api/v1/query/stream",
            json={"query": "hello", "session_id": "sess_1"},
        )
        events = self._parse_sse(resp.text)

        phases = [e["data"]["phase"] for e in events if e["event"] == "phase"]
        assert phases == [
            "intake",
            "planning",
            "retrieval",
            "generation",
            "critic",
            "completed",
        ]

    def test_emits_token_events(self, client: TestClient):
        """Token events should contain decoded tokens that join to the answer."""
        resp = client.post(
            "/api/v1/query/stream",
            json={"query": "hello", "session_id": "sess_1"},
        )
        events = self._parse_sse(resp.text)

        tokens = [e["data"]["token"] for e in events if e["event"] == "token"]
        assert "".join(tokens) == "Hello world!"

    def test_emits_metadata_event(self, client: TestClient):
        """The last event should be metadata with answer, query, and chunk count."""
        resp = client.post(
            "/api/v1/query/stream",
            json={"query": "hello", "session_id": "sess_1"},
        )
        events = self._parse_sse(resp.text)

        metadata_events = [e for e in events if e["event"] == "metadata"]
        assert len(metadata_events) == 1
        meta = metadata_events[0]["data"]
        assert meta["query"] == "hello"
        assert "world" in meta["answer"]
        assert meta["chunks_retrieved"] > 0
        assert meta["status"] == "completed"

    def test_metadata_includes_grounding_score(self, client: TestClient):
        """The metadata event should include a ``grounding_score`` field."""
        resp = client.post(
            "/api/v1/query/stream",
            json={"query": "hello", "session_id": "sess_1"},
        )
        events = self._parse_sse(resp.text)
        meta = [e for e in events if e["event"] == "metadata"][0]
        assert "grounding_score" in meta["data"]

    def test_error_if_query_missing(self, client: TestClient):
        """The endpoint should reject requests without a query."""
        resp = client.post(
            "/api/v1/query/stream",
            json={"session_id": "sess_1"},
        )
        assert resp.status_code == 422  # Validation error

    def test_handles_cache_hit(self, client: TestClient, test_app: FastAPI):
        """When the cache has a hit, the endpoint returns immediately."""
        # Override deps with a cache-hitting stub for this test
        cache_deps = _DummyDeps()
        cache_deps.query_cache.get_cached_query.return_value = {
            "answer": "cached answer"
        }
        test_app.state.svc = cache_deps

        resp = client.post(
            "/api/v1/query/stream",
            json={"query": "hello", "session_id": "sess_cache"},
        )
        events = self._parse_sse(resp.text)

        # Should have exactly 3 events: phase (cache_hit), token, metadata
        assert len(events) == 3
        assert events[0]["event"] == "phase"
        assert events[0]["data"]["phase"] == "cache_hit"
        assert events[1]["event"] == "token"
        assert events[1]["data"]["token"] == "cached answer"
        assert events[2]["event"] == "metadata"
        assert events[2]["data"]["status"] == "cached"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])