from typing import List, Dict, Any, Optional
import asyncio
from opentelemetry import trace
from backend.storage.vector.chroma import ChromaStore
from backend.storage.vector.bm25 import bm25_retriever
from backend.storage.graph.neo4j import graph_store
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
    def __init__(self, chroma_store: ChromaStore):
        self.chroma = chroma_store
        self.bm25 = bm25_retriever
        self.graph = graph_store
        self.rrf_k = 60

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

            with tracer.start_as_current_span("vector_search") as vs_span:
                vs_span.set_attribute("engine", "chroma")
                vs_span.set_attribute("n_results", k * 2)
                chroma_raw, sparse_results, graph_results = await asyncio.gather(
                    asyncio.to_thread(self.chroma.query, query, n_results=k*2, tenant_id=tid),
                    asyncio.to_thread(self.bm25.retrieve, query, k=k*2),
                    asyncio.to_thread(self._retrieve_from_graph, query)
                )
                vs_span.set_attribute("result_count", len(chroma_raw.get("documents", [[]])[0]) if chroma_raw.get("documents") else 0)

            # Parse Dense Retrieval (Chroma)
            vector_results = []
            if isinstance(chroma_raw, dict) and chroma_raw.get("documents") and chroma_raw["documents"]:
                for i in range(len(chroma_raw["documents"][0])):
                    raw_meta = chroma_raw["metadatas"][0][i] if chroma_raw.get("metadatas") else {}
                    metadata = {
                        METADATA_TENANT_KEY: raw_meta.get(METADATA_TENANT_KEY, tid),
                        METADATA_DOCUMENT_KEY: raw_meta.get(METADATA_DOCUMENT_KEY, ""),
                        METADATA_CHUNK_KEY: raw_meta.get(METADATA_CHUNK_KEY, ""),
                        **{k: v for k, v in raw_meta.items()
                           if k not in (METADATA_TENANT_KEY, METADATA_DOCUMENT_KEY, METADATA_CHUNK_KEY)},
                    }
                    vector_results.append({
                        "content": chroma_raw["documents"][0][i],
                        "metadata": metadata,
                        "chunk_id": metadata.get(METADATA_CHUNK_KEY, ""),
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
                            }
                        fused_scores[content]["score"] += weight * (1.0 / (self.rrf_k + rank + 1))

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
        if not self.graph or not getattr(self.graph, "_driver", None):
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