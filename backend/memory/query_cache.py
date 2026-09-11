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

    def _similarity_from_distance(self, distance: float) -> float:
        """Convert cosine distance (0=identical, 2=opposite) to similarity 0-1."""
        try:
            d = float(distance)
        except Exception:
            return 0.0
        # Clamp distance to [0,2], similarity = 1 - d (for unit vectors) then clamp to [0,1]
        # Previously buggy: if similarity <0: similarity = 1 - similarity produced >1 values
        sim = 1.0 - d
        return max(0.0, min(1.0, sim))

    async def get_cached_query_async(self, query: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        tracer = get_tracer()
        with tracer.start_as_current_span("cache_read") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("tenant_id", resolve_tenant_id(tenant_id))
            span.set_attribute("provider", self._provider)
            try:
                if self._vector_store is not None:
                    if hasattr(self._vector_store, "query_async"):
                        results = await self._vector_store.query_async(query, n_results=1, tenant_id=tenant_id)
                    else:
                        import asyncio
                        results = await asyncio.to_thread(self._vector_store.query, query, n_results=1, tenant_id=tenant_id)
                    if not results.get("documents") or not results["documents"][0]:
                        span.set_attribute("hit", False)
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return None
                    distance = results["distances"][0][0] if results.get("distances") and results["distances"][0] else 1.0
                    similarity = self._similarity_from_distance(distance)
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

    def get_cached_query(self, query: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # Sync wrapper for backward compat; delegates to async if loop not running
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Inside async context but called sync — use threadpool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self.get_cached_query_async(query, tenant_id)).result()
            return asyncio.run(self.get_cached_query_async(query, tenant_id))
        except RuntimeError:
            import asyncio
            return asyncio.run(self.get_cached_query_async(query, tenant_id))
        except Exception as e:
            logger.debug("Sync cache fallback failed, trying direct sync query", error=str(e))
            # Fallback to legacy sync query
            tracer = get_tracer()
            with tracer.start_as_current_span("cache_read_sync_fallback") as span:
                try:
                    results = self._vector_store.query(query, n_results=1, tenant_id=tenant_id) if self._vector_store else None
                    if not results or not results.get("documents") or not results["documents"][0]:
                        return None
                    distance = results["distances"][0][0] if results.get("distances") and results["distances"][0] else 1.0
                    similarity = self._similarity_from_distance(distance)
                    if similarity >= self.similarity_threshold:
                        meta = results["metadatas"][0][0] if results.get("metadatas") and results["metadatas"][0] else {}
                        answer = meta.get("answer") if isinstance(meta, dict) else None
                        if answer:
                            return {"answer": answer, "metadata": meta}
                    return None
                except Exception as e2:
                    logger.error("Cache lookup failed", error=str(e2))
                    return None

    async def cache_query_async(self, query: str, answer: str, metadata: Dict[str, Any] = None, tenant_id: Optional[str] = None) -> None:
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
                    if hasattr(self._vector_store, "add_chunks_async"):
                        await self._vector_store.add_chunks_async([query], [enriched], [str(uuid.uuid4())], tenant_id=tid)
                    else:
                        import asyncio
                        await asyncio.to_thread(self._vector_store.add_chunks, [query], [enriched], [str(uuid.uuid4())], tenant_id=tid)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    logger.info("Query cached (vector)", query_preview=query[:60], tenant_id=tid)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error("Cache store failed", error=str(e))

    def cache_query(self, query: str, answer: str, metadata: Dict[str, Any] = None, tenant_id: Optional[str] = None) -> None:
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Fire-and-forget in async context to avoid blocking
                loop.create_task(self.cache_query_async(query, answer, metadata, tenant_id))
                return
            asyncio.run(self.cache_query_async(query, answer, metadata, tenant_id))
        except RuntimeError:
            import asyncio
            try:
                asyncio.run(self.cache_query_async(query, answer, metadata, tenant_id))
            except Exception as e:
                logger.error("Cache store failed", error=str(e))
        except Exception as e:
            logger.error("Cache store failed", error=str(e))

    async def clear_tenant_cache_async(self, tenant_id: str) -> int:
        """Invalidate all cached queries for a tenant (called on document delete)."""
        tid = resolve_tenant_id(tenant_id)
        try:
            if self._vector_store and hasattr(self._vector_store, "_get_sessionmaker"):
                maker = self._vector_store._get_sessionmaker()
                from sqlalchemy import text
                async with maker() as session:
                    result = await session.execute(text(f"DELETE FROM {self._vector_cache_table} WHERE tenant_id = :tid"), {"tid": tid})
                    await session.commit()
                    return result.rowcount if hasattr(result, "rowcount") else 0
            elif self._vector_store and hasattr(self._vector_store, "_engine_maker"):
                _, maker = self._vector_store._engine_maker()
                from sqlalchemy import text
                async with maker() as session:
                    result = await session.execute(text(f"DELETE FROM {self._vector_cache_table} WHERE tenant_id = :tid"), {"tid": tid})
                    await session.commit()
                    return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as e:
            logger.warning("Cache invalidation failed", error=str(e), tenant_id=tid)
        return 0

    def clear_tenant_cache(self, tenant_id: str) -> int:
        try:
            import asyncio
            return asyncio.run(self.clear_tenant_cache_async(tenant_id))
        except Exception:
            return 0
