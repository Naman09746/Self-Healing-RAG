"""Factory for vector stores — centralizes provider selection and fallback."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.vector.base import VectorStore

logger = get_logger(__name__)


def get_vector_store(collection_name: str | None = None) -> VectorStore:
    """Create a VectorStore based on settings.VECTOR_STORE_PROVIDER.

    Supported providers: chroma, pgvector, qdrant, pinecone.
    Falls back to Chroma with warning if provider unavailable.
    """
    provider = (getattr(settings, "VECTOR_STORE_PROVIDER", "chroma") or "chroma").lower().strip()
    logger.info("Initializing vector store", provider=provider, collection_name=collection_name)

    if provider == "pgvector":
        try:
            from backend.storage.vector.pgvector import PgVectorStore

            return PgVectorStore(collection_name=collection_name)  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to initialize PgVectorStore, falling back to Chroma", error=str(e))
            if not getattr(settings, "VECTOR_LEGACY_FALLBACK", True):
                raise

    if provider == "qdrant":
        try:
            from backend.storage.vector.qdrant import QdrantStore

            return QdrantStore(collection_name=collection_name)  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to initialize QdrantStore, falling back to Chroma", error=str(e))
            if not getattr(settings, "VECTOR_LEGACY_FALLBACK", True):
                raise

    if provider == "pinecone":
        try:
            from backend.storage.vector.pinecone import PineconeStore

            return PineconeStore(collection_name=collection_name)  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to initialize PineconeStore, falling back to Chroma", error=str(e))
            if not getattr(settings, "VECTOR_LEGACY_FALLBACK", True):
                raise

    # Default / fallback: Chroma
    from backend.storage.vector.chroma import ChromaStore

    if collection_name:
        return ChromaStore(collection_name=collection_name)  # type: ignore[return-value]
    return ChromaStore()  # type: ignore[return-value]
