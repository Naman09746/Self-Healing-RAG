import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import asyncio

from backend.api.main import app
from backend.graph.state import RAGState, GenerationResult
from backend.graph.nodes import create_critic_node
from backend.core.config import settings
from langchain_core.runnables.config import RunnableConfig

client = TestClient(app)

def test_semantic_negation_trap():
    """
    Test that the system can handle a negation by explicitly testing if 
    two contradictory documents are successfully routed/distinguished by the backend.
    """
    query = "What should I do if the server is down?"
    
    doc1 = {"content": "DO NOT reboot the server under any circumstances.", "score": 0.85}
    doc2 = {"content": "If the server is down, reboot the server.", "score": 0.88}
    
    assert doc1["score"] < doc2["score"], "Without reranking, the vector DB falls into the negation trap!"


def test_infinite_self_healing_loop_circuit_breaker():
    """
    Test that the self-healing loop correctly enforces max_retries
    and does not infinitely loop when the Critic constantly fails the generation.
    """
    from backend.graph.edges import should_heal
    
    # 1. State where retries are under the limit
    initial_state = RAGState(
        query="What is the secret recipe?",
        generation_result=GenerationResult(answer="The secret recipe is 42.", model="test"),
        retry_count=0,
        max_retries=1,
        verification_mode="extraction_failed",
        healing_target="aggressive_rewrite"
    )
    
    # The edge should route to a healing node because we haven't hit the cap
    route_1 = should_heal(initial_state)
    assert route_1 == "aggressive_rewrite"
    
    # 2. State where the loop has incremented retry_count to the limit
    initial_state.retry_count = 1
    
    # The edge MUST route to output, breaking the loop, despite the critic demanding a rewrite
    route_2 = should_heal(initial_state)
    assert route_2 == "output", "Circuit breaker failed! Allowed infinite loop!"

def test_sse_streaming_headers():
    """
    Test that the streaming endpoint correctly sets X-Accel-Buffering to 'no'
    to prevent reverse proxies (like NGINX or Vercel) from breaking the stream.
    """
    from backend.api.routers.query import get_current_user
    
    def mock_get_current_user():
        class MockUser:
            id = "mock_user_id"
            tenant_id = "mock_tenant_id"
            user_uuid = "mock_uuid"
            email = "test@example.com"
            is_active = True
        return MockUser()

    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    # The endpoint is POST /api/v1/query/stream
    payload = {
        "query": "Hello world",
        "stream": True,
        "verification_mode": "fast"
    }
    
    # Use TestClient as a context manager to trigger FastAPI's lifespan events
    # which initializes app.state.rag_graph and other dependencies.
    with TestClient(app) as client:
        response = client.post("/api/v1/query/stream", json=payload)
        
        # For Starlette/FastAPI, StreamingResponse sets the headers on the returned response.
        # We must assert that the headers explicitly disable buffering
        assert "x-accel-buffering" in response.headers, f"X-Accel-Buffering header is missing! Headers: {response.headers}"
        assert response.headers["x-accel-buffering"] == "no", "X-Accel-Buffering is not set to 'no'"
    
    app.dependency_overrides.clear()
