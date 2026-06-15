import uuid
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from backend.ingestion.loaders import DocumentLoader
from backend.ingestion.chunker import Chunker
from backend.storage.vector.chroma import ChromaStore
from backend.storage.vector.bm25 import bm25_retriever
from backend.storage.graph.neo4j import graph_store
from backend.agents.generation.llm_client import LLMClient
from backend.core.logging import get_logger
from backend.storage.tenant import resolve_tenant_id

logger = get_logger(__name__)


class IngestionPipeline:
    def __init__(self):
        self.loader = DocumentLoader()
        self.chunker = Chunker()
        self.vector_store = ChromaStore()
        self.graph_store = graph_store
        self.bm25 = bm25_retriever
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

            # 3. Prepare metadata with deterministic, content-addressed chunk IDs
            #    Each Chunk object carries a SHA-256-based chunk_id derived from
            #    its text. This ensures: idempotent re-ingestion, traceability,
            #    and stable chunk-level citations.
            doc_id = str(uuid.uuid4())
            file_name = Path(file_path).name
            tid = resolve_tenant_id(tenant_id)
            ids = [c.chunk_id for c in chunks]
            texts = [c.text for c in chunks]
            metadatas = [
                {
                    "document_id": doc_id,
                    "file_name": file_name,
                    "chunk_index": i,
                    "chunk_id": ids[i],
                }
                for i in range(len(chunks))
            ]

            # 4. Dense Store (ChromaDB) — tenant_id is stamped at the storage layer
            self.vector_store.add_chunks(texts, metadatas, ids, tenant_id=tid)

            # 5. Sparse Store (BM25) — wraps in try/except to avoid partial index
            try:
                current_corpus = self.bm25.corpus + texts
                current_metadata = self.bm25.metadata + metadatas
                self.bm25.index(current_corpus, current_metadata)
            except Exception as e:
                logger.error("BM25 indexing failed, rolling back vector store", error=str(e))
                # Rollback: remove the chunks we just added to ChromaDB
                for chunk_id in ids:
                    try:
                        self.vector_store.collection.delete(ids=[chunk_id])
                    except Exception:
                        pass
                raise

            # 6. GraphRAG (Neo4j Entity Extraction using local LLM agent)
            # Process the first 3 chunks to build a high-quality knowledge graph without slowing ingestion
            try:
                await self._extract_and_store_graph(texts[:3], doc_id)
            except Exception as e:
                logger.warning("Graph extraction failed, but vector and sparse stores are intact", error=str(e))

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
