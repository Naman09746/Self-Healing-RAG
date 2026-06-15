import uuid
import chromadb
from typing import Optional, Dict, Any
from opentelemetry import trace
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.storage.tenant import tenant_collection_name, metadata_filter, resolve_tenant_id, enrich_metadata

logger = get_logger(__name__)


class QueryCache:
    """Tenant-aware semantic query cache.

    Each tenant gets an isolated ChromaDB collection named
    ``query_cache__{sanitized_tenant_id}`` so that cached answers
    from one tenant are never semantically matched against queries
    from another tenant. The default collection ``query_cache``
    is used for the default tenant, maintaining backward compatibility.

    Design:
    - Documents stored = the QUERY text (for semantic similarity lookup)
    - Answer stored as metadata field "answer"
    - Lookup: embed incoming query, find nearest stored query, return its answer
    - Tenant scope: enforced via per-tenant collection naming
    """

    BASE_COLLECTION = "query_cache"

    def __init__(self):
        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            self.client.heartbeat()
        except Exception:
            self.client = chromadb.PersistentClient(path="./chroma_data")

        # Default collection for backward compatibility with existing data
        self.default_collection = self.client.get_or_create_collection(
            name=self.BASE_COLLECTION
        )
        # Tenant-scoped collections are lazily created in _get_collection
        self._collections: Dict[str, Any] = {}
        self.similarity_threshold = 0.92  # Slightly relaxed for better hit rate

    def _get_collection(self, tenant_id: Optional[str] = None) -> Any:
        """Return the tenant-scoped collection, creating it if needed.

        Uses the base collection for the default tenant for backward
        compatibility with existing cached data.
        """
        tid = resolve_tenant_id(tenant_id)
        if tid == settings.DEFAULT_TENANT_ID:
            return self.default_collection
        if tid not in self._collections:
            coll_name = tenant_collection_name(self.BASE_COLLECTION, tid)
            self._collections[tid] = self.client.get_or_create_collection(name=coll_name)
        return self._collections[tid]

    def get_cached_query(self, query: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return cached answer for a semantically similar query, or None on miss.

        Args:
            query: The user's query text.
            tenant_id: Tenant scope. Uses the default tenant if not provided.

        Returns:
            A dict with ``answer`` and ``metadata`` keys, or ``None`` on cache miss.
        """
        tracer = get_tracer()
        with tracer.start_as_current_span("cache_read") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("tenant_id", resolve_tenant_id(tenant_id))
            try:
                collection = self._get_collection(tenant_id)
                results = collection.query(
                    query_texts=[query],
                    n_results=1,
                )

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
        """Cache a query→answer pair, scoped to the caller's tenant.

        Args:
            query: The user's query text (embedded for similarity search).
            answer: The generated answer (stored in metadata).
            metadata: Additional metadata to store alongside the answer.
            tenant_id: Tenant scope. Uses the default tenant if not provided.
        """
        tracer = get_tracer()
        with tracer.start_as_current_span("cache_write") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("answer_length", len(answer))
            span.set_attribute("tenant_id", resolve_tenant_id(tenant_id))
            try:
                collection = self._get_collection(tenant_id)
                combined_meta = {"answer": answer, **(metadata or {})}
                tid = resolve_tenant_id(tenant_id)
                enriched = [enrich_metadata(combined_meta, tid)]
                collection.add(
                    documents=[query],   # ← embed the QUERY (not the answer)
                    metadatas=enriched,
                    ids=[str(uuid.uuid4())],
                )
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info("Query cached", query_preview=query[:60], tenant_id=resolve_tenant_id(tenant_id))
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error("Cache store failed", error=str(e))
