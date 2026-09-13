"""Unit tests for optimized chunking, embedding query cache, and retriever Jaccard deduplication."""

import pytest
from backend.ingestion.chunker import Chunker, _split_table_smartly
from backend.storage.vector.embeddings import EmbeddingProvider
from backend.storage.retriever import HybridRetriever


def test_chunker_markdown_table_preservation():
    """Test that small tables remain intact and large tables repeat header on bisection."""
    chunker = Chunker(chunk_size=150, chunk_overlap=0)
    table_text = (
        "# Pricing Plans\n\n"
        "| Tier | Monthly Price | SLA |\n"
        "|---|---|---|\n"
        "| Starter | $49 | 99.0% |\n"
        "| Pro | $199 | 99.9% |\n"
        "| Enterprise | $999 | 99.99% |\n\n"
        "End of pricing."
    )
    chunks = chunker.split_text(table_text)
    assert len(chunks) > 0
    # Header should be preserved in table chunks
    table_chunks = [c.text for c in chunks if "|" in c.text]
    assert len(table_chunks) > 0
    for tc in table_chunks:
        assert "| Tier | Monthly Price | SLA |" in tc


def test_chunker_header_hierarchy():
    """Test that headers are not arbitrarily stripped or mangled."""
    chunker = Chunker(chunk_size=120, chunk_overlap=10)
    markdown_doc = (
        "# AcmeCloud Policies\n\n"
        "## 1. Security\n\n"
        "Data is encrypted at rest using AES-256-GCM.\n\n"
        "## 2. Retention\n\n"
        "Disaster recovery snapshots persist for 90 days."
    )
    chunks = chunker.split_text(markdown_doc)
    combined = "\n".join(c.text for c in chunks)
    assert "## 1. Security" in combined
    assert "## 2. Retention" in combined


def test_embedding_query_cache_and_hash_bypass():
    """Test that embed_query caches real embeddings but does not cache hash fallback."""
    provider = EmbeddingProvider(use_hash_fallback=True)
    # Disable OpenAI key to force hash fallback
    provider._openai_key = ""
    provider._provider = "ollama"

    vec1 = provider.embed_query("test query text")
    assert len(provider._query_cache) == 0  # Not cached because it's hash fallback

    # Simulate real embedding without hash fallback flag
    provider._last_used_hash_fallback = False
    cache_key = (provider._provider, provider.model, "test query text")
    provider._query_cache[cache_key] = vec1

    # Now it hits the cache
    vec2 = provider.embed_query("test query text")
    assert vec1 == vec2
    assert len(provider._query_cache) == 1


@pytest.mark.asyncio
async def test_retriever_jaccard_deduplication():
    """Test that near-identical chunks are deduplicated post-RRF."""
    from unittest.mock import AsyncMock
    mock_vector = AsyncMock()
    mock_sparse = AsyncMock()
    retriever = HybridRetriever(vector_store=mock_vector, sparse_store=mock_sparse)

    mock_vector.query_async = AsyncMock(return_value={
        "documents": [["The policy retains backups for up to 90 days.", "The policy retains backups for up to 90 days."]],
        "metadatas": [[{"chunk_id": "c1"}, {"chunk_id": "c2"}]],
        "distances": [[0.1, 0.12]],
    })
    mock_sparse.retrieve_async = AsyncMock(return_value=[
        {"content": "Distinct unrelated chunk about API keys.", "metadata": {"chunk_id": "c3"}}
    ])

    results = await retriever.retrieve("backup retention", k=5, tenant_id="default")
    assert len(results) == 2
    # The two identical backup chunks should be deduplicated so only one appears
    backup_results = [r for r in results if "retains backups" in r["content"]]
    assert len(backup_results) == 1
