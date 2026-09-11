from typing import List, Dict, Any, Optional
import asyncio
from opentelemetry import trace
from backend.storage.vector.base import VectorStore
from backend.storage.sparse.factory import get_sparse_store
from backend.storage.graph.factory import get_graph_store
from backend.core.config import settings
# Legacy alias for callers that patched bm25_retriever directly
try:
    from backend.storage.vector.bm25 import bm25_retriever as _legacy_bm25  # noqa: F401
except Exception:
    _legacy_bm25 = None  # type: ignore
from backend.core.logging import get_logger
from backend.core.observability import get_tracer, span_with_status
from backend.storage.tenant import (
    resolve_tenant_id,
    metadata_filter,
    audit_retrieval,
    hash_query_text,
    METADATA_TENANT_KEY,
    METADATA_DOCUMENT_KEY,
    METADATA_CHUNK_KEY,
)

logger = get_logger(__name__)

class HybridRetriever:
    def __init__(
        self,
        vector_store: VectorStore,
        chroma_store: Optional[VectorStore] = None,
        sparse_store=None,
        graph_store_override=None,
    ):
        # Support both positional arg names: HybridRetriever(store) and legacy HybridRetriever(chroma_store=...)
        store = chroma_store if chroma_store is not None else vector_store
        self.vector_store: VectorStore = store
        self.chroma = self.vector_store
        # Pluggable sparse/graph via factories (free-tier defaults: pg_tsvector / memory)
        try:
            self.bm25 = sparse_store or get_sparse_store()
        except Exception:
            # Fallback to legacy bm25 if factory not available (e.g. tests patching)
            from backend.storage.vector.bm25 import bm25_retriever as _fb

            self.bm25 = _fb  # type: ignore[assignment]
        try:
            self.graph = graph_store_override or get_graph_store()
        except Exception:
            from backend.storage.graph.neo4j import graph_store as _gfb

            self.graph = _gfb  # type: ignore[assignment]
        self.rrf_k = 60

    @property
    def vector_engine(self) -> str:
        prov = getattr(settings, "VECTOR_STORE_PROVIDER", "pgvector")
        # normalize
        return str(prov).lower() if prov else "pgvector"

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        tenant_id: Optional[str] = None,
        user_uuid: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Perform tenant-scoped hybrid retrieval using RRF to fuse Vector and BM25 results."""
        tracer = get_tracer()
        tid = resolve_tenant_id(tenant_id)
        query_hash = hash_query_text(query)
        logger.info("Starting hybrid retrieval", query=query, k=k, tenant_id=tid)

        with tracer.start_as_current_span("retrieval") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("k", k)
            span.set_attribute("tenant_id", tid)
            span.set_attribute("session_id", session_id or "")

            # 1, 2, 3. Execute all retrievals in parallel for performance
            chroma_raw: Dict[str, Any]
            sparse_results: List[Dict[str, Any]]
            graph_results: List[str]

            async def _safe_graph_retrieve() -> List[str]:
                try:
                    return await asyncio.wait_for(
                        asyncio.to_thread(self._retrieve_from_graph, query),
                        timeout=3.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Graph retrieval timed out after 3.0s, proceeding with vector/sparse results", query=query[:60])
                    return []
                except Exception as e:
                    logger.warning("Graph retrieval failed, continuing without graph", error=str(e))
                    return []

            with tracer.start_as_current_span("vector_search") as vs_span:
                vs_span.set_attribute("engine", self.vector_engine)
                vs_span.set_attribute("sparse_provider", getattr(settings, "SPARSE_PROVIDER", "pg_tsvector"))
                vs_span.set_attribute("n_results", k * 2)

                async def _dense_retrieve() -> Dict[str, Any]:
                    if hasattr(self.chroma, "query_async"):
                        return await self.chroma.query_async(query, n_results=k * 2, tenant_id=tid)
                    return await asyncio.to_thread(self.chroma.query, query, n_results=k * 2, tenant_id=tid)

                async def _sparse_retrieve() -> List[Dict[str, Any]]:
                    if hasattr(self.bm25, "retrieve_async"):
                        try:
                            return await self.bm25.retrieve_async(query, k=k * 2, tenant_id=tid)
                        except TypeError:
                            return await self.bm25.retrieve_async(query, k=k * 2)
                    def _sync():
                        try:
                            return self.bm25.retrieve(query, k=k * 2, tenant_id=tid)
                        except TypeError:
                            return self.bm25.retrieve(query, k=k * 2)
                    return await asyncio.to_thread(_sync)

                chroma_raw, sparse_results, graph_results = await asyncio.gather(
                    _dense_retrieve(),
                    _sparse_retrieve(),
                    _safe_graph_retrieve(),
                )
                vs_span.set_attribute("result_count", len(chroma_raw.get("documents", [[]])[0]) if chroma_raw.get("documents") else 0)

            # Parse Dense Retrieval (provider-agnostic: all stores return Chroma-compatible dict)
            vector_results = []
            distances0 = []
            if isinstance(chroma_raw, dict) and chroma_raw.get("documents") and chroma_raw["documents"]:
                docs0 = chroma_raw["documents"][0] if chroma_raw["documents"] else []
                metas0 = chroma_raw["metadatas"][0] if chroma_raw.get("metadatas") and chroma_raw["metadatas"] else [{} for _ in docs0]
                distances0 = chroma_raw.get("distances", [[]])[0] if chroma_raw.get("distances") else [None for _ in docs0]
                if len(distances0) < len(docs0):
                    distances0 = list(distances0) + [None] * (len(docs0) - len(distances0))
                for i in range(len(docs0)):
                    raw_meta = metas0[i] if i < len(metas0) and isinstance(metas0[i], dict) else {}
                    metadata = {
                        METADATA_TENANT_KEY: raw_meta.get(METADATA_TENANT_KEY, tid),
                        METADATA_DOCUMENT_KEY: raw_meta.get(METADATA_DOCUMENT_KEY, ""),
                        METADATA_CHUNK_KEY: raw_meta.get(METADATA_CHUNK_KEY, ""),
                        **{k: v for k, v in raw_meta.items()
                           if k not in (METADATA_TENANT_KEY, METADATA_DOCUMENT_KEY, METADATA_CHUNK_KEY)},
                    }
                    dist = distances0[i] if i < len(distances0) else None
                    try:
                        dist_f = float(dist) if dist is not None else None
                    except Exception:
                        dist_f = None
                    vector_results.append({
                        "content": docs0[i],
                        "metadata": metadata,
                        "chunk_id": metadata.get(METADATA_CHUNK_KEY, ""),
                        "distance": dist_f,
                    })

            # 4. Reciprocal Rank Fusion (RRF)
            with tracer.start_as_current_span("rrf_fusion") as rrf_span:
                fused_scores = {}

                def update_scores(results, weight=1.0):
                    for rank, res in enumerate(results):
                        content = res["content"]
                        if content not in fused_scores:
                            fused_scores[content] = {
                                "score": 0.0,
                                "metadata": res.get("metadata", {}),
                                "chunk_id": res.get("chunk_id", ""),
                                "distance": res.get("distance", None),
                            }
                        fused_scores[content]["score"] += weight * (1.0 / (self.rrf_k + rank + 1))
                        d = res.get("distance", None)
                        if d is not None:
                            cur = fused_scores[content].get("distance")
                            if cur is None or d < cur:
                                fused_scores[content]["distance"] = d

                update_scores(vector_results, weight=1.0)
                update_scores(sparse_results, weight=1.0)

                sorted_results = sorted(
                    [{"content": c, **v} for c, v in fused_scores.items()],
                    key=lambda x: x["score"],
                    reverse=True
                )

                final_results = sorted_results[:k]
                rrf_span.set_attribute("candidates", len(fused_scores))
                rrf_span.set_attribute("final_count", len(final_results))

            # Add graph context as independent entries with knowledge_graph source
            if isinstance(graph_results, list) and graph_results:
                graph_entries = [
                    {
                        "content": result,
                        "metadata": {
                            "source": "knowledge_graph",
                            METADATA_TENANT_KEY: tid,
                            METADATA_DOCUMENT_KEY: "",
                            METADATA_CHUNK_KEY: "",
                        },
                        "chunk_id": "",
                    }
                    for result in graph_results
                ]
                # Score graph entries via RRF as if they were rank-ordered
                offset = len(fused_scores)
                for idx, entry in enumerate(graph_entries):
                    content = entry["content"]
                    if content not in fused_scores:
                        rank = offset + idx
                        fused_scores[content] = {
                            "score": 1.0 / (self.rrf_k + rank + 1),
                            "metadata": entry["metadata"],
                            "chunk_id": entry["chunk_id"],
                            "distance": None,
                        }
                # Re-sort after adding graph entries
                final_results = sorted(
                    [{"content": c, **v} for c, v in fused_scores.items()],
                    key=lambda x: x["score"],
                    reverse=True
                )[:k]
                span.set_attribute("graph_results", len(graph_results))

            # Audit log the retrieval operation
            audit_record = audit_retrieval(
                tenant_id=tid,
                operation="retrieve",
                query_text_hash=query_hash,
                chunk_count=len(final_results),
                success=True,
                user_uuid=user_uuid,
                session_id=session_id,
            )
            if audit_record:
                logger.info("Retrieval audit", **audit_record)

            span.set_attribute("result_count", len(final_results))
            span.set_status(trace.Status(trace.StatusCode.OK))

        return final_results

    def _retrieve_from_graph(self, query: str) -> List[str]:
        """Extract entities from query and traverse relationships in a single batched Cypher query."""
        if not self.graph or not hasattr(self.graph, "query_graph"):
            return []
        if getattr(self.graph, "_driver", None) is None and self.graph.__class__.__name__ not in ("InMemoryGraphStore",):
            provider = getattr(settings, "GRAPH_PROVIDER", "memory") or "memory"
            if provider.lower() != "memory":
                return []

        tracer = get_tracer()
        with tracer.start_as_current_span("graph_search") as span:
            # Simple stop words to avoid useless graph lookups
            stop_words = {"what", "who", "where", "how", "when", "why", "is", "the", "and", "a", "an", "to", "in", "of", "for", "with"}
            keywords = [w.strip("?.,!") for w in query.lower().split() if w.lower() not in stop_words and len(w) > 3]
            span.set_attribute("keywords_count", len(keywords))

            if not keywords:
                span.set_attribute("results_count", 0)
                return []

            results = []
            cypher = (
                "MATCH (e)-[r]->(related) "
                "WHERE toLower(e.name) IN $names "
                "RETURN e.name, type(r), related.name LIMIT 15"
            )
            try:
                graph_data = self.graph.query_graph(cypher, {"names": keywords})
                if graph_data:
                    for record in graph_data:
                        results.append(f"{record['e.name']} {record['type(r)']} {record['related.name']}")
            except Exception as e:
                logger.error("Batched graph query failed", error=str(e))

            unique_results = list(set(results))
            span.set_attribute("results_count", len(unique_results))
            return unique_results