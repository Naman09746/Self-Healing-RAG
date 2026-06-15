"""Unit tests for the ChromaStore add_chunks SHA-256 fallback.

These tests verify that when `ids` is empty/None, ChromaStore
auto-generates deterministic SHA-256 chunk IDs.
"""

import pytest
import hashlib
from unittest.mock import patch, MagicMock, PropertyMock
from backend.storage.vector.chroma import ChromaStore


@pytest.fixture
def mock_chroma():
    """Create a ChromaStore instance with all external dependencies mocked."""
    with patch("backend.storage.vector.chroma.chromadb") as mock_chromadb, \
         patch("backend.storage.vector.chroma.settings") as mock_settings, \
         patch("backend.storage.vector.chroma.embedding_functions") as mock_ef:

        # Configure settings
        mock_settings.CHROMA_HOST = "localhost"
        mock_settings.CHROMA_PORT = 8000
        mock_settings.CHROMA_ALLOW_RESET = False
        mock_settings.CHROMA_COLLECTION_NAME = "test_collection"
        mock_settings.OLLAMA_HOST = "http://localhost:11434"

        # Mock the collection
        mock_collection = MagicMock()
        mock_chromadb.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        store = ChromaStore(collection_name="test_collection")
        store.collection = mock_collection
        return store


def test_add_chunks_ids_provided(mock_chroma):
    """When ids are provided, they should be used as-is."""
    chunks = ["chunk1 text", "chunk2 text"]
    metadatas = [{"doc": "a"}, {"doc": "b"}]
    ids = ["id-1", "id-2"]

    mock_chroma.add_chunks(chunks, metadatas, ids)

    mock_chroma.collection.add.assert_called_once()
    call_kwargs = mock_chroma.collection.add.call_args.kwargs
    assert call_kwargs["ids"] == ["id-1", "id-2"]


def test_add_chunks_ids_none_fallback(mock_chroma):
    """When ids is None, SHA-256 hashes should be auto-generated."""
    chunks = ["chunk1 text", "chunk2 text"]
    metadatas = [{"doc": "a"}, {"doc": "b"}]

    expected_ids = [
        hashlib.sha256(c.encode("utf-8")).hexdigest()[:48]
        for c in chunks
    ]

    mock_chroma.add_chunks(chunks, metadatas, ids=None)

    mock_chroma.collection.add.assert_called_once()
    call_kwargs = mock_chroma.collection.add.call_args.kwargs
    assert call_kwargs["ids"] == expected_ids


def test_add_chunks_ids_empty_list_fallback(mock_chroma):
    """When ids is an empty list, SHA-256 hashes should be auto-generated."""
    chunks = ["chunk1 text", "chunk2 text"]
    metadatas = [{"doc": "a"}, {"doc": "b"}]

    expected_ids = [
        hashlib.sha256(c.encode("utf-8")).hexdigest()[:48]
        for c in chunks
    ]

    mock_chroma.add_chunks(chunks, metadatas, ids=[])

    mock_chroma.collection.add.assert_called_once()
    call_kwargs = mock_chroma.collection.add.call_args.kwargs
    assert call_kwargs["ids"] == expected_ids


def test_add_chunks_fallback_deterministic(mock_chroma):
    """Same chunks should produce same auto-generated IDs across calls."""
    chunks = ["reproducible text"]
    metadatas = [{"doc": "a"}]

    mock_chroma.add_chunks(chunks, metadatas, ids=None)
    id_call_1 = mock_chroma.collection.add.call_args.kwargs["ids"]

    mock_chroma.collection.reset_mock()

    mock_chroma.add_chunks(chunks, metadatas, ids=None)
    id_call_2 = mock_chroma.collection.add.call_args.kwargs["ids"]

    assert id_call_1 == id_call_2


def test_add_chunks_ids_truthiness_edge_cases(mock_chroma):
    """Chunks with empty string in ids list should use provided value, not fallback."""
    chunks = ["chunk1"]
    metadatas = [{"doc": "a"}]
    ids = [""]  # empty string is falsy but list is not empty

    mock_chroma.add_chunks(chunks, metadatas, ids=ids)

    mock_chroma.collection.add.assert_called_once()
    call_kwargs = mock_chroma.collection.add.call_args.kwargs
    # Empty string should be passed through (ids list is truthy)
    assert call_kwargs["ids"] == [""]