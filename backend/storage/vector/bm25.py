"""Backward-compatible shim — prefer `backend.storage.sparse.factory.get_sparse_store`."""

from backend.storage.sparse.memory_bm25 import BM25SparseStore as BM25Retriever  # noqa: F401
from backend.storage.sparse.memory_bm25 import BM25SparseStore
from backend.core.logging import get_logger

logger = get_logger(__name__)


class BM25Error(Exception):
    """Raised when BM25 indexing or retrieval encounters a fatal error."""


# Singleton for legacy callers (`from backend.storage.vector.bm25 import bm25_retriever`)
# Uses BM25SparseStore which is tenant-aware and compatible
bm25_retriever = BM25SparseStore()
