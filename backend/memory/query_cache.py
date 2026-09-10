import uuid
from typing import Optional, Dict, Any
from opentelemetry import trace
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.storage.tenant import tenant_collection_name, metadata_filter, resolve_tenant_id, enrich_metadata

logger = get_logger(__name__)


class QueryCache:
    """Tenant-aware semantic query cache with pluggable vector backend.

    Chroma path: per-tenant collections ``query_cache__{tid}`` (legacy).
    pgvector/Qdrant/Pinecone path: delegated to a VectorStore with query text as document
    and answer in metadata, tenant-scoped via store's filtering.
    """

    BASE_COLLECTION = "query_cache"

    def __init__(self):
        self.similarity_threshold = 0.92
        self._provider = (getattr(settings, "VECTOR_STORE_PROVIDER", "chroma") or "chroma").lower()
        self._vector_store = None
        self._vector_cache_table = "query_cache_chunks"

        if self._provider in ("pgvector", "qdrant", "pinecone"):
            try:
                if self._provider == "pgvector":
                    from backend.storage.vector.pgvector import PgVectorStore

                    # Dedicated table for cache to avoid mixing with main chunks; but reuse same store logic
                    self._vector_store = PgVectorStore(table=self._vector_cache_table)
                elif self._provider == "qdrant":
                    from backend.storage.vector.qdrant import QdrantStore

                    self._vector_store = QdrantStore(collection_name=self.BASE_COLLECTION, is_cache=True)  # type: ignore[call-arg]
                elif self._provider == "pinecone":
                    from backend.storage.vector.pinecone import PineconeStore

                    self._vector_store = PineconeStore(is_cache=True)  # type: ignore[call-arg]
                logger.info("QueryCache using provider", provider=self._provider)
            except Exception as e:
                logger.warning("QueryCache vector provider failed, falling back to Chroma", error=str(e), provider=self._provider)
                self._provider = "chroma"
                self._vector_store = None

        if self._provider == "chroma" or self._vector_store is None:
            import chromadb

            try:
                self.client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                )
                self.client.heartbeat()
            except Exception:
                self.client = chromadb.PersistentClient(path="./chroma_data")
            self.default_collection = self.client.get_or_create_collection(name=self.BASE_COLLECTION)
            self._collections: Dict[str, Any] = {}
        else:
            self.client = None
            self.default_collection = None
            self._collections = {}

    def _get_collection(self, tenant_id: Optional[str] = None) -> Any:
        """Return the tenant-scoped Chroma collection (only for chroma provider)."""
        tid = resolve_tenant_id(tenant_id)
        if tid == settings.DEFAULT_TENANT_ID:
            return self.default_collection
        if tid not in self._collections:
            coll_name = tenant_collection_name(self.BASE_COLLECTION, tid)
            self._collections[tid] = self.client.get_or_create_collection(name=coll_name)
        return self._collections[tid]

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
                # Chroma path
                collection = self._get_collection(tenant_id)
                results = collection.query(query_texts=[query], n_results=1)
                if not results["documents"] or not results["documents"][0]:
                    span.set_attribute("hit", False)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return None
                distance = results["distances"][0][0]
                similarity = 1.0 - distance
                span.set_attribute("similarity", round(similarity, 4))
                if similarity >= self.similarity_threshold:
                    meta = results["metadatas"][0][0]
                    answer = meta.get("answer")
                    if answer:
                        span.set_attribute("hit", True)
                        span.set_attribute("answer_length", len(answer))
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        logger.info("Cache hit", similarity=round(similarity, 3), tenant_id=resolve_tenant_id(tenant_id))
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
                    return
                collection = self._get_collection(tenant_id)
                combined_meta = {"answer": answer, **(metadata or {})}
                tid = resolve_tenant_id(tenant_id)
                enriched = [enrich_metadata(combined_meta, tid)]
                collection.add(documents=[query], metadatas=enriched, ids=[str(uuid.uuid4())])
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info("Query cached", query_preview=query[:60], tenant_id=resolve_tenant_id(tenant_id))
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error("Cache store failed", error=str(e))
