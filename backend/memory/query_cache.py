import uuid
from typing import Optional, Dict, Any
from opentelemetry import trace
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.storage.tenant import tenant_collection_name, metadata_filter, resolve_tenant_id, enrich_metadata

logger = get_logger(__name__)


class QueryCache:
    """Tenant-aware semantic query cache with pluggable vector backend (pgvector, Qdrant, Pinecone).
    
    Delegates caching to a VectorStore with query text as document and answer in metadata,
    tenant-scoped via store's filtering.
    """

    BASE_COLLECTION = "query_cache"

    def __init__(self):
        self.similarity_threshold = 0.92
        self._provider = (getattr(settings, "VECTOR_STORE_PROVIDER", "pgvector") or "pgvector").lower()
        self._vector_store = None
        self._vector_cache_table = "query_cache_chunks"

        if self._provider == "pgvector" or self._provider not in ("qdrant", "pinecone"):
            from backend.storage.vector.pgvector import PgVectorStore

            # Dedicated table for cache to avoid mixing with main chunks; but reuse same store logic
            self._vector_store = PgVectorStore(table=self._vector_cache_table)
            self._provider = "pgvector"
        elif self._provider == "qdrant":
            from backend.storage.vector.qdrant import QdrantStore

            self._vector_store = QdrantStore(collection_name=self.BASE_COLLECTION, is_cache=True)  # type: ignore[call-arg]
        elif self._provider == "pinecone":
            from backend.storage.vector.pinecone import PineconeStore

            self._vector_store = PineconeStore(is_cache=True)  # type: ignore[call-arg]
        
        logger.info("QueryCache using provider", provider=self._provider)

    def get_cached_query(self, query: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        tracer = get_tracer()
        with tracer.start_as_current_span("cache_read") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("tenant_id", resolve_tenant_id(tenant_id))
            span.set_attribute("provider", self._provider)
            try:
                if self._vector_store is not None:
                    # pgvector/qdrant/pinecone path: use VectorStore.query
                    results = self._vector_store.query(query, n_results=1, tenant_id=tenant_id)
                    if not results.get("documents") or not results["documents"][0]:
                        span.set_attribute("hit", False)
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return None
                    distance = results["distances"][0][0] if results.get("distances") and results["distances"][0] else 1.0
                    # pgvector distance is cosine distance (0=identical), chroma also; normalize to similarity
                    similarity = 1.0 - float(distance)
                    # For stores returning similarity directly, distance may already be similarity; handle both
                    if similarity < 0:
                        similarity = 1.0 - similarity
                    span.set_attribute("similarity", round(similarity, 4))
                    if similarity >= self.similarity_threshold:
                        meta = results["metadatas"][0][0] if results.get("metadatas") and results["metadatas"][0] else {}
                        answer = meta.get("answer") if isinstance(meta, dict) else None
                        if answer:
                            span.set_attribute("hit", True)
                            span.set_attribute("answer_length", len(answer))
                            span.set_status(trace.Status(trace.StatusCode.OK))
                            logger.info("Cache hit (vector)", similarity=round(similarity, 3), tenant_id=resolve_tenant_id(tenant_id))
                            return {"answer": answer, "metadata": meta}
                    span.set_attribute("hit", False)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return None
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("hit", False)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error("Cache lookup failed", error=str(e))
                return None

    def cache_query(self, query: str, answer: str, metadata: Dict[str, Any] = None, tenant_id: Optional[str] = None) -> None:
        tracer = get_tracer()
        with tracer.start_as_current_span("cache_write") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("answer_length", len(answer))
            span.set_attribute("tenant_id", resolve_tenant_id(tenant_id))
            try:
                if self._vector_store is not None:
                    combined_meta = {"answer": answer, **(metadata or {})}
                    tid = resolve_tenant_id(tenant_id)
                    enriched = enrich_metadata(combined_meta, tid)
                    self._vector_store.add_chunks([query], [enriched], [str(uuid.uuid4())], tenant_id=tid)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    logger.info("Query cached (vector)", query_preview=query[:60], tenant_id=tid)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error("Cache store failed", error=str(e))
