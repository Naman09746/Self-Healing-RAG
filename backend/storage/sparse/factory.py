"""Factory for SparseStore."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def get_sparse_store():
    provider = (getattr(settings, "SPARSE_PROVIDER", "pg_tsvector") or "pg_tsvector").lower().strip()
    logger.info("Initializing sparse store", provider=provider)

    if provider == "pg_tsvector":
        try:
            from backend.storage.sparse.pg_tsvector import PgTsvectorSparseStore

            return PgTsvectorSparseStore()
        except Exception as e:
            logger.error("Failed to init PgTsvectorSparseStore, falling back to bm25", error=str(e))

    if provider == "bm25":
        from backend.storage.sparse.memory_bm25 import BM25SparseStore

        return BM25SparseStore()

    # Default / fallback: bm25 memory
    from backend.storage.sparse.memory_bm25 import BM25SparseStore

    return BM25SparseStore()
