"""Factory for vector stores — centralizes provider selection."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.vector.base import VectorStore

logger = get_logger(__name__)


def get_vector_store(collection_name: str | None = None) -> VectorStore:
    """Create a VectorStore based on settings.VECTOR_STORE_PROVIDER.

    Supported providers: pgvector (default $0 free-tier), qdrant, pinecone.
    """
    provider = (getattr(settings, "VECTOR_STORE_PROVIDER", "pgvector") or "pgvector").lower().strip()
    logger.info("Initializing vector store", provider=provider, collection_name=collection_name)

    if provider == "qdrant":
        try:
            from backend.storage.vector.qdrant import QdrantStore

            return QdrantStore(collection_name=collection_name)  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to initialize QdrantStore", error=str(e))
            raise

    if provider == "pinecone":
        try:
            from backend.storage.vector.pinecone import PineconeStore

            return PineconeStore(collection_name=collection_name)  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to initialize PineconeStore", error=str(e))
            raise

    # Default: PostgreSQL pgvector
    from backend.storage.vector.pgvector import PgVectorStore

    return PgVectorStore(collection_name=collection_name)  # type: ignore[return-value]
