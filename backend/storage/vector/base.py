"""Vector store abstraction — pluggable backends for dense retrieval."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    """Protocol that every dense vector store must implement.

    All stores return a Chroma-compatible dict to keep
    ``HybridRetriever`` parsing unchanged:

        {"documents": [[...]], "metadatas": [[...]], "distances": [[...]], "ids": [[...]]}

    This allows zero-change migration for RRF fusion in
    ``backend/storage/retriever.py``.
    """

    def add_chunks(
        self,
        chunks: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
        tenant_id: str | None = None,
    ) -> None:
        ...

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        ...

    def delete_document(
        self,
        document_id: str,
        tenant_id: str | None = None,
    ) -> None:
        ...

    def heartbeat(self) -> bool:
        """Return True if the store is reachable."""
        ...

    def count(self, tenant_id: str | None = None) -> int:
        """Number of vectors visible to tenant (for health/monitoring)."""
        ...


class VectorStoreError(RuntimeError):
    """Raised when a vector store operation fails fatally."""


class VectorDimMismatchError(VectorStoreError):
    """Raised when an embedding dimension does not match the store's configured dim."""
