"""Unit tests for multi-query retrieval and query expansion."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.storage.retriever import HybridRetriever, _compute_jaccard, _dedup_by_jaccard
from backend.agents.healer.query_rewriter import QueryRewriter
from backend.graph.state import RAGState
from backend.graph.nodes import create_planning_node, create_retrieval_node, create_healing_node
from backend.core.config import settings


def test_jaccard_similarity_and_deduplication():
    """Verify Jaccard calculation and list deduplication."""
    assert _compute_jaccard("apple banana cherry", "apple banana cherry") == 1.0
    assert _compute_jaccard("apple banana cherry", "orange grape kiwi") == 0.0
    assert _compute_jaccard("", "apple") == 0.0

    candidates = [
        {"content": "apple banana cherry date", "score": 0.9},
        {"content": "apple banana cherry date", "score": 0.8},  # identical
        {"content": "completely different content here", "score": 0.5},
    ]
    deduped = _dedup_by_jaccard(candidates, threshold=0.8)
    assert len(deduped) == 2
    assert deduped[0]["score"] == 0.9
    assert deduped[1]["score"] == 0.5


@pytest.mark.asyncio
async def test_retrieve_many_empty_and_single_query():
    """Verify retrieve_many handles empty and single queries gracefully."""
    mock_vector = AsyncMock()
    mock_sparse = AsyncMock()
    retriever = HybridRetriever(vector_store=mock_vector, sparse_store=mock_sparse)

    # Empty list
    res = await retriever.retrieve_many([])
    assert res == []

    # All whitespace
    res = await retriever.retrieve_many(["   ", ""])
    assert res == []

    # Single query delegation
    mock_vector.query_async = AsyncMock(return_value={
        "documents": [["Test doc content"]],
        "metadatas": [[{"chunk_id": "c1"}]],
        "distances": [[0.1]],
    })
    mock_sparse.retrieve_async = AsyncMock(return_value=[])

    single_res = await retriever.retrieve_many(["single query"], k=3)
    assert len(single_res) == 1
    assert single_res[0]["content"] == "Test doc content"


@pytest.mark.asyncio
async def test_retrieve_many_fusion_and_weighting():
    """Verify multiple queries run concurrently, fuse via RRF, and apply variant weights."""
    mock_vector = AsyncMock()
    mock_sparse = AsyncMock()
    retriever = HybridRetriever(vector_store=mock_vector, sparse_store=mock_sparse)

    # Patch retrieve directly to observe fusion behavior
    async def mock_retrieve(query, k=5, **kwargs):
        if "query1" in query:
            return [
                {"content": "Doc Alpha (relevant to q1)", "score": 0.03, "distance": 0.2, "metadata": {}, "chunk_id": "c1"},
                {"content": "Shared Doc (relevant to both)", "score": 0.02, "distance": 0.3, "metadata": {}, "chunk_id": "c_shared"},
            ]
        elif "query2" in query:
            return [
                {"content": "Shared Doc (relevant to both)", "score": 0.03, "distance": 0.15, "metadata": {}, "chunk_id": "c_shared"},
                {"content": "Doc Beta (relevant to q2)", "score": 0.02, "distance": 0.4, "metadata": {}, "chunk_id": "c2"},
            ]
        return []

    with patch.object(retriever, "retrieve", side_effect=mock_retrieve):
        results = await retriever.retrieve_many(["query1", "query2"], k=5)

    assert len(results) == 3
    # Shared doc appeared in both queries, so it should receive fused RRF score from both
    contents = [r["content"] for r in results]
    assert "Shared Doc (relevant to both)" in contents
    assert "Doc Alpha (relevant to q1)" in contents
    assert "Doc Beta (relevant to q2)" in contents

    # The shared doc should preserve the minimum distance (0.15 vs 0.3)
    shared_result = next(r for r in results if r["content"] == "Shared Doc (relevant to both)")
    assert shared_result["distance"] == 0.15


@pytest.mark.asyncio
async def test_retrieve_many_handles_subquery_failure():
    """If one sub-retrieval fails, remaining sub-retrievals still fuse successfully."""
    mock_vector = AsyncMock()
    mock_sparse = AsyncMock()
    retriever = HybridRetriever(vector_store=mock_vector, sparse_store=mock_sparse)

    async def mock_retrieve(query, k=5, **kwargs):
        if "failing" in query:
            raise RuntimeError("Database connection timed out")
        return [{"content": "Successful doc", "score": 0.05, "distance": 0.1, "metadata": {}, "chunk_id": "c_ok"}]

    with patch.object(retriever, "retrieve", side_effect=mock_retrieve):
        results = await retriever.retrieve_many(["failing query", "working query"], k=5)

    assert len(results) == 1
    assert results[0]["content"] == "Successful doc"


@pytest.mark.asyncio
async def test_query_rewriter_expand_query():
    """Verify expand_query parses multiple lines and falls back properly."""
    rewriter = QueryRewriter()

    # Mock LLM generation
    rewriter.client.generate = AsyncMock(
        return_value="1. alternative search phrasing\n2. synonym technical concept\n3. broader query terms"
    )

    expanded = await rewriter.expand_query("original test query", error_context="missing docs", max_variants=2)
    assert len(expanded) >= 2
    assert "alternative search phrasing" in expanded[0] or "alternative search phrasing" in expanded[1]

    # Test error fallback
    rewriter.client.generate = AsyncMock(side_effect=RuntimeError("LLM offline"))
    fallback = await rewriter.expand_query("original test query", error_context="missing docs")
    assert fallback == ["original test query"]


@pytest.mark.asyncio
async def test_planning_node_multi_query_expansion():
    """Verify planning_node expands queries when MULTI_QUERY_ENABLED=True."""
    mock_deps = MagicMock()
    mock_planner = AsyncMock()
    mock_planner.create_plan = AsyncMock(return_value={
        "is_complex": True,
        "strategy": "HYBRID",
        "sub_queries": ["sub query 1", "sub query 2", "sub query 3"],
    })
    mock_deps.planner = mock_planner

    planning_node = create_planning_node(mock_deps)

    # Test with MULTI_QUERY_ENABLED=False (default behavior)
    with patch.object(settings, "MULTI_QUERY_ENABLED", False):
        state = RAGState(query="What is the refund policy and SLA for enterprise tier?")
        result = await planning_node(state)
        assert result["expanded_queries"] == ["What is the refund policy and SLA for enterprise tier?"]

    # Test with MULTI_QUERY_ENABLED=True and complex query
    with patch.object(settings, "MULTI_QUERY_ENABLED", True):
        with patch.object(settings, "MULTI_QUERY_MAX_VARIANTS", 3):
            state = RAGState(query="What is the refund policy and SLA for enterprise tier?")
            result = await planning_node(state)
            assert len(result["expanded_queries"]) == 3
            assert result["expanded_queries"][0] == "What is the refund policy and SLA for enterprise tier?"
            assert result["expanded_queries"][1] == "sub query 1"
            assert result["expanded_queries"][2] == "sub query 2"


@pytest.mark.asyncio
async def test_retrieval_node_multi_query_routing():
    """Verify retrieval_node calls retrieve_many when MULTI_QUERY_ENABLED and multiple queries exist."""
    mock_deps = MagicMock()
    mock_deps.telemetry_collector = None
    mock_retriever = AsyncMock()
    mock_retriever.retrieve_many = AsyncMock(return_value=[
        {"content": "Retrieved doc via multi-query", "score": 0.05, "distance": 0.2, "metadata": {}, "chunk_id": "c1"}
    ])
    mock_retriever.retrieve = AsyncMock(return_value=[])
    mock_deps.hybrid_retriever = mock_retriever

    mock_reranker = AsyncMock()
    mock_reranker.rerank = AsyncMock(side_effect=lambda q, items, top_k: items[:top_k])
    mock_deps.reranker = mock_reranker

    retrieval_node = create_retrieval_node(mock_deps)

    state = RAGState(
        query="Main query",
        expanded_queries=["Main query", "Variant query 1"],
        target_k=3,
    )

    with patch.object(settings, "MULTI_QUERY_ENABLED", True):
        res = await retrieval_node(state)
        mock_retriever.retrieve_many.assert_awaited_once()
        mock_retriever.retrieve.assert_not_awaited()
        assert len(res["retrieved_chunks"]) == 1
