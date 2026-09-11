import uuid
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from backend.ingestion.loaders import DocumentLoader
from backend.ingestion.chunker import Chunker
from backend.storage.vector.factory import get_vector_store
from backend.storage.sparse.factory import get_sparse_store
from backend.storage.graph.factory import get_graph_store
from backend.agents.generation.llm_client import LLMClient
from backend.core.logging import get_logger
from backend.core.config import settings
from backend.storage.tenant import resolve_tenant_id, deterministic_chunk_id

logger = get_logger(__name__)


class IngestionPipeline:
    def __init__(self, vector_store=None, sparse_store=None, graph_store=None):
        self.loader = DocumentLoader()
        self.chunker = Chunker()
        self.vector_store = vector_store or get_vector_store()
        # Pluggable sparse/graph via factories (free-tier: pg_tsvector / memory)
        try:
            self.bm25 = sparse_store or get_sparse_store()
        except Exception as e:
            logger.warning("Could not init sparse store via factory, falling back to bm25", error=str(e))
            from backend.storage.vector.bm25 import bm25_retriever as _fb

            self.bm25 = _fb  # type: ignore[assignment]
        try:
            self.graph_store = graph_store or get_graph_store()
        except Exception as e:
            logger.warning("Could not init graph store via factory, falling back", error=str(e))
            from backend.storage.graph.neo4j import graph_store as _gfb

            self.graph_store = _gfb  # type: ignore[assignment]
        self.llm = LLMClient()

    async def ingest_file(self, file_path: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Ingest a single file into Hybrid, Sparse, and Graph storage.

        Args:
            file_path: Path to the document file to ingest.
            tenant_id: The tenant this document belongs to. Falls back
                       to the configured default tenant.

        Returns:
            Dict with document_id, file_name, chunk_count, and storage.

        Raises:
            RuntimeError: If ingestion fails partway through. Some stores
                          may have been written — the caller should consider
                          this document partially ingested.
        """
        logger.info("Starting Advanced Ingestion", file_path=file_path, tenant_id=resolve_tenant_id(tenant_id))

        try:
            # 1. Load document
            text = self.loader.load_document(file_path)

            # 2. Chunk text
            chunks = self.chunker.split_text(text)

            # 3. Prepare metadata with deterministic, tenant-scoped chunk IDs
            #    Uses deterministic_chunk_id(tenant_id, document_id, chunk_index, content)
            #    to ensure cross-tenant isolation and idempotent re-ingestion.
            doc_id = str(uuid.uuid4())
            file_name = Path(file_path).name
            tid = resolve_tenant_id(tenant_id)
            texts = [c.text for c in chunks]
            ids = [deterministic_chunk_id(tid, doc_id, i, c.text) for i, c in enumerate(chunks)]
            metadatas = [
                {
                    "document_id": doc_id,
                    "file_name": file_name,
                    "chunk_index": i,
                    "chunk_id": ids[i],
                    "content_hash": chunks[i].chunk_id,
                }
                for i in range(len(chunks))
            ]

            # 4. Dense Store (provider-agnostic) — tenant_id is stamped at the storage layer
            import asyncio as _asyncio
            if hasattr(self.vector_store, "add_chunks_async"):
                await self.vector_store.add_chunks_async(texts, metadatas, ids, tenant_id=tid)
            elif hasattr(self.vector_store, "_add_chunks_async"):
                await self.vector_store._add_chunks_async(texts, metadatas, ids, tenant_id=tid)
            else:
                await _asyncio.to_thread(self.vector_store.add_chunks, texts, metadatas, ids, tenant_id=tid)

            # 5. Sparse Store — tenant-aware, incremental (pg_tsvector) or rebuilt (bm25 memory)
            try:
                sparse_provider = getattr(settings, "SPARSE_PROVIDER", "pg_tsvector")
                if hasattr(self.bm25, "index_async") and sparse_provider == "pg_tsvector":
                    try:
                        await self.bm25.index_async(texts, metadatas, tenant_id=tid)
                    except TypeError:
                        await self.bm25.index_async(texts, metadatas)
                elif sparse_provider == "pg_tsvector":
                    # PG tsvector supports incremental upsert — just index new chunks
                    try:
                        self.bm25.index(texts, metadatas, tenant_id=tid)  # type: ignore[call-arg]
                    except TypeError:
                        self.bm25.index(texts, metadatas)  # legacy sig
                else:
                    # BM25 memory: rebuild per-tenant corpus (preserve tenant isolation)
                    try:
                        # Try tenant-aware retrieval of existing corpus if available
                        existing = []
                        existing_meta = []
                        if hasattr(self.bm25, "_corpora"):
                            existing = self.bm25._corpora.get(tid, [])  # type: ignore[attr-defined]
                            existing_meta = self.bm25._metas.get(tid, [])  # type: ignore[attr-defined]
                        elif hasattr(self.bm25, "corpus"):
                            existing = self.bm25.corpus  # type: ignore[attr-defined]
                            existing_meta = self.bm25.metadata  # type: ignore[attr-defined]
                        full_corpus = existing + texts
                        full_meta = existing_meta + metadatas
                        try:
                            self.bm25.index(full_corpus, full_meta, tenant_id=tid)  # type: ignore[call-arg]
                        except TypeError:
                            self.bm25.index(full_corpus, full_meta)
                    except Exception:
                        # Fallback to legacy global rebuild
                        current_corpus = (getattr(self.bm25, "corpus", []) or []) + texts
                        current_metadata = (getattr(self.bm25, "metadata", []) or []) + metadatas
                        self.bm25.index(current_corpus, current_metadata)
            except Exception as e:
                logger.error("Sparse indexing failed, rolling back vector store", error=str(e))
                # Rollback: remove document chunks from vector and sparse stores by document_id
                try:
                    import asyncio as _aio2
                    if hasattr(self.vector_store, "delete_document_async"):
                        await self.vector_store.delete_document_async(doc_id, tenant_id=tid)
                    elif hasattr(self.vector_store, "delete_document"):
                        await _aio2.to_thread(self.vector_store.delete_document, doc_id, tenant_id=tid)
                except Exception as re:
                    logger.warning("Vector rollback failed", error=str(re))
                try:
                    if hasattr(self.bm25, "delete_document_async"):
                        await self.bm25.delete_document_async(doc_id, tenant_id=tid)
                    elif hasattr(self.bm25, "delete_document"):
                        self.bm25.delete_document(doc_id, tenant_id=tid)
                except Exception:
                    pass
                raise

            # 6. GraphRAG — gated by GRAPH_EXTRACTION_ENABLED (default False for free-tier)
            if getattr(settings, "GRAPH_EXTRACTION_ENABLED", False):
                try:
                    import asyncio as _aio3
                    await _aio3.wait_for(self._extract_and_store_graph(texts[:2], doc_id), timeout=8.0)
                except asyncio.TimeoutError:
                    logger.warning("Graph extraction timed out after 8s, proceeding")
                except Exception as e:
                    logger.warning("Graph extraction failed, but vector and sparse stores are intact", error=str(e))
            else:
                logger.debug("Graph extraction skipped (GRAPH_EXTRACTION_ENABLED=False)")

            logger.info("Advanced Ingestion complete", doc_id=doc_id, chunks=len(chunks))

            return {
                "document_id": doc_id,
                "file_name": file_name,
                "chunk_count": len(chunks),
                "storage": ["vector", "sparse", "graph"],
            }
        except Exception as e:
            logger.error("Ingestion failed", error=str(e), file_path=file_path)
            raise RuntimeError(f"Ingestion failed for {file_path}: {e}") from e

    async def _extract_and_store_graph(self, chunks: List[str], doc_id: str):
        """Extract rich entities and relationships from chunks using the LLM agent."""
        logger.info("Extracting graph nodes and edges using local LLM agent")

        for i, chunk in enumerate(chunks):
            prompt = f"""You are a GraphRAG knowledge engineer. Extract key entities and relationships from the given text chunk.

TEXT CHUNK:
{chunk}

Extract:
1. Entities: Any key term, concept, person, organization, location, or technology.
2. Relationships: How these entities are connected to each other.

Respond ONLY with a JSON object in this format (no preamble or explanation):
{{
  "entities": [
    {{"name": "Entity Name", "type": "Concept|Person|Organization|Location|Technology", "description": "Brief description"}}
  ],
  "relationships": [
    {{"source": "Entity Name 1", "target": "Entity Name 2", "relation": "RELATED_TO|MEMBER_OF|PART_OF|LOCATED_IN", "context": "Brief context"}}
  ]
}}
"""
            try:
                response_str = await self.llm.generate(prompt, format="json")
                start = response_str.find("{")
                end = response_str.rfind("}") + 1

                if start >= 0 and end > start:
                    data = json.loads(response_str[start:end])

                    # 1. Store Entities
                    for ent in data.get("entities", []):
                        name = ent.get("name")
                        ent_type = ent.get("type", "Concept")
                        desc = ent.get("description", "")
                        if name:
                            self.graph_store.add_entity(
                                name, ent_type, {"source": doc_id, "description": desc}
                            )

                    # 2. Store Relationships
                    for rel in data.get("relationships", []):
                        source = rel.get("source")
                        target = rel.get("target")
                        relation = rel.get("relation", "RELATED_TO")
                        context = rel.get("context", "")
                        if source and target:
                            # Ensure both nodes exist
                            self.graph_store.add_entity(source, "Concept", {"source": doc_id})
                            self.graph_store.add_entity(target, "Concept", {"source": doc_id})
                            self.graph_store.add_relationship(
                                source, target, relation, {"context": context}
                            )

                logger.info(f"Processed graph chunk {i+1}/{len(chunks)}")
            except json.JSONDecodeError as e:
                logger.error("LLM returned invalid JSON for graph extraction", error=str(e))
            except Exception as e:
                logger.error("LLM Graph extraction failed for chunk", error=str(e))
