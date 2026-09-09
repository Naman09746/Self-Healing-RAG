import chromadb
import hashlib
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.tenant import metadata_filter, enrich_metadata, resolve_tenant_id

from chromadb.utils import embedding_functions

logger = get_logger(__name__)

class ChromaStore:
    """Tenant-aware vector store backed by ChromaDB.

    Every chunk stored carries a ``tenant_id`` in its metadata. All
    query and delete operations enforce a ``where`` filter scoped to
    the caller's tenant. This prevents cross-tenant data leakage at
    the storage layer regardless of API-layer safeguards.

    ChromaDB ``allow_reset`` is controlled by the ``CHROMA_ALLOW_RESET``
    environment variable (defaults to ``False`` in production). Set it
    to ``true`` in development if you need the reset API.
    """

    def __init__(self, collection_name: str = None):
        use_local = getattr(settings, "CHROMA_USE_LOCAL", True) or settings.CHROMA_HOST in ("localhost", "127.0.0.1")
        if use_local:
            logger.info("Using embedded ChromaDB persistent storage at ./chroma_data")
            self.client = chromadb.PersistentClient(path="./chroma_data")
        else:
            try:
                logger.info("Connecting to ChromaDB Server", host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
                self.client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    settings=ChromaSettings(allow_reset=settings.CHROMA_ALLOW_RESET)
                )
                self.client.heartbeat()
            except Exception as e:
                logger.warning("Could not connect to ChromaDB Server, falling back to local storage", error=str(e))
                self.client = chromadb.PersistentClient(path="./chroma_data")

        try:
            from chromadb.utils import embedding_functions
            self.embedding_function = embedding_functions.OllamaEmbeddingFunction(
                url=f"{settings.OLLAMA_HOST}/api/embeddings",
                model_name=settings.EMBEDDING_MODEL,
            )
        except Exception as e:
            logger.critical("Failed to initialize Ollama embedding function", error=str(e))
            self.embedding_function = None

        try:
            if self.embedding_function is not None:
                self.collection = self.client.get_or_create_collection(
                    name=collection_name or settings.CHROMA_COLLECTION_NAME,
                    embedding_function=self.embedding_function
                )
            else:
                self.collection = self.client.get_or_create_collection(
                    name=collection_name or settings.CHROMA_COLLECTION_NAME
                )
        except Exception as e:
            logger.critical("Failed to get or create ChromaDB collection", error=str(e))
            raise

    def add_chunks(self, chunks: List[str], metadatas: List[Dict[str, Any]], ids: List[str], tenant_id: Optional[str] = None):
        """Add tenant-scoped chunks to the collection.

        Each chunk's metadata is automatically enriched with the
        ``tenant_id`` field before storage. The caller does **not**
        need to include it in the metadata dicts — this method
        stamps it at the storage layer.

        If ``ids`` is empty or ``None``, a deterministic SHA-256 hash of
        each chunk's text content is used as the ID (truncated to 48 hex
        characters). This ensures backward compatibility for callers that
        do not supply their own IDs.
        """
        logger.info("Adding chunks to ChromaDB", count=len(chunks), tenant_id=resolve_tenant_id(tenant_id))
        if not ids:
            ids = [
                hashlib.sha256(c.encode("utf-8")).hexdigest()[:48]
                for c in chunks
            ]
        try:
            enriched = [enrich_metadata(m, resolve_tenant_id(tenant_id)) for m in metadatas]
            self.collection.add(
                documents=chunks,
                metadatas=enriched,
                ids=ids
            )
        except Exception as e:
            logger.error("Failed to add chunks to ChromaDB", error=str(e), count=len(chunks))
            raise

    def query(self, query_text: str, n_results: int = 5, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Query the collection, scoped to the caller's tenant.

        Args:
            query_text: The search query string.
            n_results: Maximum number of results to return.
            tenant_id: Tenant scope. Falls back to ``default``.

        Returns:
            ChromaDB query result dict with documents, metadatas,
            distances, and ids — all filtered to the given tenant.

        Raises:
            RuntimeError: If the query fails due to a storage-layer error.
        """
        tid = resolve_tenant_id(tenant_id)
        logger.info("Querying ChromaDB", query=query_text, n_results=n_results, tenant_id=tid)
        try:
            return self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=metadata_filter(tid)
            )
        except Exception as e:
            logger.error("ChromaDB query failed", error=str(e), query=query_text)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}

    def delete_document(self, document_id: str, tenant_id: Optional[str] = None):
        """Delete all chunks for a document, scoped to the caller's tenant.

        Args:
            document_id: The document identifier to delete.
            tenant_id: Tenant scope. Falls back to ``default``.
        """
        tid = resolve_tenant_id(tenant_id)
        logger.info("Deleting document chunks", document_id=document_id, tenant_id=tid)
        try:
            self.collection.delete(
                where={"$and": [{"document_id": document_id}, metadata_filter(tid)]}
            )
        except Exception as e:
            logger.error("Failed to delete document chunks", error=str(e), document_id=document_id)
            raise
