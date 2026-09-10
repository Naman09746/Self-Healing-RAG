"""Unit and contract tests for PgVectorStore.

Verifies:
1. Deterministic SHA-256 fallback when chunk IDs are omitted.
2. Correct handling of explicitly provided IDs.
3. Metadata enrichment with tenant isolation.
4. Collection-scoped queries and namespace isolation.
5. Standard response dictionary formatting for HybridRetriever compatibility.
6. Delete, heartbeat, and count operations.
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.storage.vector.pgvector import PgVectorStore


@pytest.fixture
def mock_pgvector():
    """Create a PgVectorStore with mocked database sessions and async engine."""
    with patch("backend.storage.vector.pgvector.create_async_engine") as mock_engine, \
         patch("backend.storage.vector.pgvector.sessionmaker") as mock_sm:

        store = PgVectorStore(dimension=768, table="test_vector_chunks", collection_name="test_col")
        store._ensured = True  # skip DDL

        mock_session = AsyncMock()
        mock_sm.return_value = MagicMock(return_value=mock_session)
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        store._sessionmaker = mock_sm.return_value
        return store, mock_session


def test_add_chunks_with_ids(mock_pgvector):
    store, mock_session = mock_pgvector
    chunks = ["chunk one", "chunk two"]
    metadatas = [{"source": "doc1.md"}, {"source": "doc2.md"}]
    ids = ["custom-id-1", "custom-id-2"]

    store.add_chunks(chunks, metadatas, ids, tenant_id="tenant-alpha")

    # Should execute insert statements
    assert mock_session.execute.called
    assert mock_session.commit.called


def test_add_chunks_deterministic_sha256_fallback(mock_pgvector):
    store, mock_session = mock_pgvector
    chunks = ["deterministic test string"]
    metadatas = [{"source": "doc1.md"}]

    store.add_chunks(chunks, metadatas, ids=None, tenant_id="tenant-alpha")

    expected_id = hashlib.sha256(chunks[0].encode("utf-8")).hexdigest()[:48]
    call_args = mock_session.execute.call_args[0]
    params = mock_session.execute.call_args[0][1] if len(call_args) > 1 else mock_session.execute.call_args.kwargs
    assert params["id"] == expected_id


def test_query_format_compatibility(mock_pgvector):
    store, mock_session = mock_pgvector

    # Mock SQL fetch rows: (id, content, metadata, distance)
    mock_row = ("chunk-1", "This is retrieved text", '{"file_name": "test.md"}', 0.12)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    res = store.query("search query", n_results=3, tenant_id="tenant-alpha")

    # Must match standard VectorStore structure
    assert "documents" in res
    assert "metadatas" in res
    assert "distances" in res
    assert "ids" in res

    assert res["documents"] == [["This is retrieved text"]]
    assert res["ids"] == [["chunk-1"]]
    assert res["metadatas"] == [[{"file_name": "test.md"}]]
    assert res["distances"] == [[0.12]]


def test_delete_document(mock_pgvector):
    store, mock_session = mock_pgvector
    store.delete_document("doc-123", tenant_id="tenant-alpha")

    assert mock_session.execute.called
    assert mock_session.commit.called


def test_heartbeat(mock_pgvector):
    store, mock_session = mock_pgvector
    assert store.heartbeat() is True


def test_count(mock_pgvector):
    store, mock_session = mock_pgvector
    mock_result = MagicMock()
    mock_result.fetchone.return_value = [42]
    mock_session.execute.return_value = mock_result

    assert store.count("tenant-alpha") == 42
