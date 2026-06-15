"""Unit tests for the Chunker with deterministic content-addressed chunk IDs."""

import hashlib
import pytest
from backend.ingestion.chunker import Chunker, Chunk


SAMPLE_TEXT = (
    "This is a sample document that should be split into multiple chunks "
    "based on the chunk size and overlap settings. "
    "It contains enough content to produce at least two chunks with "
    "the default configuration in tests. "
    "The quick brown fox jumps over the lazy dog. "
    "Python is a high-level, interpreted programming language. "
    "Machine learning and artificial intelligence are transforming "
    "many industries. "
    "Data science combines statistics, computer science, and domain expertise. "
    "Natural language processing enables computers to understand text. "
    "Deep learning uses neural networks with multiple layers."
)


def test_chunker_returns_chunk_objects():
    """Chunker.split_text should return a list of Chunk objects."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split_text(SAMPLE_TEXT)

    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunk_has_text_and_id():
    """Each Chunk should have non-empty text and chunk_id attributes."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split_text(SAMPLE_TEXT)

    for c in chunks:
        assert isinstance(c.text, str) and len(c.text) > 0
        assert isinstance(c.chunk_id, str) and len(c.chunk_id) > 0


def test_chunk_id_is_sha256_based():
    """chunk_id should be the first 48 hex chars of SHA-256 of the chunk text."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split_text(SAMPLE_TEXT)

    for c in chunks:
        expected_id = hashlib.sha256(c.text.encode("utf-8")).hexdigest()[:48]
        assert c.chunk_id == expected_id


def test_chunk_id_is_deterministic():
    """Same input text should produce identical chunk IDs."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks_1 = chunker.split_text(SAMPLE_TEXT)
    chunks_2 = chunker.split_text(SAMPLE_TEXT)

    assert len(chunks_1) == len(chunks_2)
    for c1, c2 in zip(chunks_1, chunks_2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.text == c2.text


def test_chunk_id_is_48_chars():
    """chunk_id should be exactly 48 hex characters."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split_text(SAMPLE_TEXT)

    for c in chunks:
        assert len(c.chunk_id) == 48
        # Verify it's valid hex
        int(c.chunk_id, 16)


def test_chunk_id_changes_when_text_changes():
    """Different chunk text should produce different chunk IDs."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split_text(SAMPLE_TEXT)

    ids = {c.chunk_id for c in chunks}
    # All chunk IDs should be unique (no collisions within the document)
    assert len(ids) == len(chunks)


def test_chunker_custom_sizes():
    """Chunker should respect custom chunk_size and chunk_overlap."""
    chunker = Chunker(chunk_size=50, chunk_overlap=5)
    chunks = chunker.split_text(SAMPLE_TEXT)

    assert len(chunks) > 0
    # With small chunk_size we should get more chunks than with large
    large_chunker = Chunker(chunk_size=500, chunk_overlap=0)
    large_chunks = large_chunker.split_text(SAMPLE_TEXT)

    assert len(chunks) > len(large_chunks)


def test_empty_text():
    """Splitting empty text should return an empty list."""
    chunker = Chunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split_text("")
    assert len(chunks) == 0


def test_chunk_dataclass_slots():
    """Chunk should use __slots__ for memory efficiency."""
    c = Chunk(chunk_id="abc", text="hello")
    with pytest.raises(AttributeError):
        c.non_existent_field = "should fail"