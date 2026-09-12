"""Unit tests for the streaming RAG pipeline (Phase 4B).

Tests verify that ``stream_rag_pipeline`` correctly:
- Short-circuits on cache hits, yielding a single metadata event
- Yields phase, token, and metadata events during a normal pipeline run
- Swallows ``asyncio.CancelledError`` cleanly on client disconnect
- Yields an ``error`` event and continues when the pipeline raises
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.graph.stream_runner import stream_rag_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect(agen):
    """Synchronously drain an async generator, returning a list of events."""
    async def _drain():
        events = []
        async for item in agen:
            events.append(item)
        return events
    return asyncio.run(_drain())


def _parse_sse_events(raw: list[str]) -> list[dict]:
    """Convert raw SSE text frames into a list of ``{event, data}`` dicts."""
    parsed = []
    for frame in raw:
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


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class _DummyDeps:
    """Minimal service container double for testing."""

    def __init__(self, *, cache_hit: bool = False):
        self.query_cache = MagicMock()
        if cache_hit:
            self.query_cache.get_cached_query.return_value = {
                "answer": "cached answer"
            }
        else:
            self.query_cache.get_cached_query.return_value = None

        # Generation agent stub — returns tokens synchronously through
        # the async generator.
        class _GenAgent:
            class _Client:
                model = "test-model"
            client = _Client()

            async def generate_answer_stream(self, query, context, history=""):
                for token in ["Hello", " ", "world", "!"]:
                    yield token

        self.generator = _GenAgent()


class _DummyGraph:
    """Minimal LangGraph stub that simulates a multi-step pipeline."""

    def __init__(self, *, fail: bool = False):
        self._fail = fail

    async def astream(self, state, config=None, stream_mode="values"):
        """Yield a sequence of state snapshots."""
        phases = ["intake", "planning", "retrieval", "generation", "critic", "completed"]
        chunks = [{"content": "ctx", "score": 0.9}]
        for i, phase in enumerate(phases):
            step = {
                "query": state.query,
                "session_id": state.session_id,
                "current_phase": phase,
                "retry_count": 0,
                "retrieved_chunks": chunks if phase != "intake" and phase != "planning" else [],
                "generation_result": {"answer": "Hello world!"},
            }
            # Simulate what the real generation node does: push tokens to
            # the token queue so the stream_runner can pick them up.
            if phase == "generation" and state._token_queue is not None:
                for token in ["Hello", " ", "world", "!"]:
                    await state._token_queue.put(token)
            yield step
        if self._fail:
            raise RuntimeError("pipeline crashed")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStreamRagPipeline:
    """Test suite for ``stream_rag_pipeline``."""

    def test_cache_hit_short_circuit(self):
        """A cached query should emit cache_hit phase + token + metadata and return."""
        events = _collect(
            stream_rag_pipeline(
                _DummyGraph(),
                _DummyDeps(cache_hit=True),
                "test query",
                session_id="sess_1",
            )
        )
        parsed = _parse_sse_events(events)

        # Should have exactly 3 events
        assert len(parsed) == 3
        assert parsed[0]["event"] == "phase"
        assert parsed[0]["data"]["phase"] == "cache_hit"
        assert parsed[1]["event"] == "token"
        assert parsed[1]["data"]["token"] == "cached answer"
        assert parsed[2]["event"] == "metadata"
        assert parsed[2]["data"]["status"] == "cached"

    def test_normal_pipeline_events(self):
        """A normal pipeline should emit phase, token, and metadata events."""
        events = _collect(
            stream_rag_pipeline(
                _DummyGraph(),
                _DummyDeps(cache_hit=False),
                "test query",
                session_id="sess_1",
            )
        )
        parsed = _parse_sse_events(events)

        # Check phase events
        phases = [p["data"]["phase"] for p in parsed if p["event"] == "phase"]
        assert phases == [
            "intake", "planning", "retrieval", "generation", "critic", "completed"
        ]

        # Check token events
        tokens = [p["data"]["token"] for p in parsed if p["event"] == "token"]
        assert "".join(tokens) == "Hello world!"

        # Check metadata event at the end
        metadata_events = [p for p in parsed if p["event"] == "metadata"]
        assert len(metadata_events) == 1
        meta = metadata_events[0]["data"]
        assert meta["query"] == "test query"
        assert meta["chunks_retrieved"] > 0

    def test_no_token_events_when_no_generation(self):
        """If the graph never reaches generation, no token events should be emitted."""

        class _NoGenGraph:
            async def astream(self, state, stream_mode="values"):
                yield {"query": state.query, "current_phase": "intake", "retry_count": 0}
                yield {"query": state.query, "current_phase": "completed", "retry_count": 0}

        events = _collect(
            stream_rag_pipeline(
                _NoGenGraph(),
                _DummyDeps(cache_hit=False),
                "no gen",
                session_id="sess_2",
            )
        )
        parsed = _parse_sse_events(events)
        tokens = [p for p in parsed if p["event"] == "token"]
        assert len(tokens) == 0

    def test_error_event_on_pipeline_failure(self):
        """If the pipeline raises, an error event should be yielded."""
        events = _collect(
            stream_rag_pipeline(
                _DummyGraph(fail=True),
                _DummyDeps(cache_hit=False),
                "fail query",
                session_id="sess_3",
            )
        )
        parsed = _parse_sse_events(events)
        error_events = [p for p in parsed if p["event"] == "error"]
        assert len(error_events) >= 1
        assert "pipeline crashed" in error_events[0]["data"]["message"]

    def test_cancelled_error_is_handled(self):
        """CancelledError should be caught so the SSE generator doesn't crash."""

        class _CancellingGraph:
            async def astream(self, state, *args, **kwargs):
                yield {"query": state.query, "current_phase": "intake", "retry_count": 0}
                raise asyncio.CancelledError()

        events = _collect(
            stream_rag_pipeline(
                _CancellingGraph(),
                _DummyDeps(cache_hit=False),
                "cancel query",
                session_id="sess_4",
            )
        )
        parsed = _parse_sse_events(events)
        # The CancelledError is re-raised up to the outer handler, which
        # yields an error event.  Ensure we don't get an unhandled exception.
        assert any(p["event"] == "error" for p in parsed)

    def test_metadata_includes_final_answer(self):
        """The metadata event should contain the ``answer`` field."""
        events = _collect(
            stream_rag_pipeline(
                _DummyGraph(),
                _DummyDeps(cache_hit=False),
                "metadata test",
                session_id="sess_5",
            )
        )
        parsed = _parse_sse_events(events)
        meta = [p for p in parsed if p["event"] == "metadata"][0]
        assert "answer" in meta["data"]
        # The generation_result's answer is "Hello world!"
        assert "world" in meta["data"]["answer"]

    def test_langgraph_checkpointer_compatibility(self):
        """Verify stream_rag_pipeline passes configurable thread_id to LangGraph with MemorySaver."""
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from backend.graph.state import RAGState

        wf = StateGraph(RAGState)
        def dummy_node(state):
            return {"current_phase": "completed", "final_answer": "Checkpointer success"}
        wf.add_node("dummy", dummy_node)
        wf.set_entry_point("dummy")
        wf.add_edge("dummy", END)

        # Compile WITH checkpointer (which strictly requires thread_id in config)
        compiled_graph = wf.compile(checkpointer=MemorySaver())

        events = _collect(
            stream_rag_pipeline(
                compiled_graph,
                _DummyDeps(cache_hit=False),
                "checkpointer query",
                session_id="sess_checkpointer_1",
            )
        )
        parsed = _parse_sse_events(events)
        error_events = [p for p in parsed if p["event"] == "error"]
        assert len(error_events) == 0, f"Expected no error, got: {error_events}"
        meta = [p for p in parsed if p["event"] == "metadata"]
        assert len(meta) == 1
        assert meta[0]["data"]["answer"] == "Checkpointer success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])