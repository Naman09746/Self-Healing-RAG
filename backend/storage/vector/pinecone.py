"""PineconeStore — Pinecone serverless vector backend."""

from __future__ import annotations

import hashlib
from typing import List, Dict, Any, Optional

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.tenant import enrich_metadata, resolve_tenant_id
from backend.storage.vector.embeddings import get_embedding_provider

logger = get_logger(__name__)


class PineconeStore:
    """Tenant-isolated Pinecone store using namespace = tenant_id."""

    def __init__(self, collection_name: Optional[str] = None, is_cache: bool = False):
        self.index_name = getattr(settings, "PINECONE_INDEX_NAME", "rag-collection")
        if is_cache:
            self.index_name = getattr(settings, "PINECONE_INDEX_NAME", "rag-collection") + "-cache"
        # collection_name param ignored for pinecone; kept for factory parity
        if collection_name and not is_cache:
            logger.info("PineconeStore ignores collection_name, using index_name", index=self.index_name)
        self.dim = getattr(settings, "VECTOR_STORE_DIM", 768)
        self.api_key = getattr(settings, "PINECONE_API_KEY", "") or ""
        self._index = None
        self._pc = None
        self._embed = get_embedding_provider()

    def _get_index(self):
        if self._index is not None:
            return self._index
        try:
            from pinecone import Pinecone

            if not self.api_key:
                raise RuntimeError("PINECONE_API_KEY not set")
            self._pc = Pinecone(api_key=self.api_key)
            # Ensure index exists — create if missing (serverless defaults)
            existing = [idx.name for idx in self._pc.list_indexes()]
            if self.index_name not in existing:
                try:
                    from pinecone import ServerlessSpec

                    spec = ServerlessSpec(cloud=getattr(settings, "PINECONE_CLOUD", "aws"), region=getattr(settings, "PINECONE_REGION", "us-east-1"))
                    self._pc.create_index(name=self.index_name, dimension=self.dim, metric="cosine", spec=spec)
                    logger.info("Created Pinecone index", index=self.index_name, dim=self.dim)
                except Exception as e:
                    logger.warning("Could not auto-create Pinecone index", error=str(e), index=self.index_name)
            self._index = self._pc.Index(self.index_name)
            return self._index
        except Exception as e:
            logger.error("Failed to init Pinecone index", error=str(e), index=self.index_name)
            raise

    def add_chunks(self, chunks: List[str], metadatas: List[Dict[str, Any]], ids: List[str], tenant_id: Optional[str] = None):
        if not chunks:
            return
        tid = resolve_tenant_id(tenant_id)
        if not ids:
            ids = [hashlib.sha256(c.encode("utf-8")).hexdigest()[:48] for c in chunks]
        if metadatas is None:
            metadatas = [{} for _ in chunks]
        enriched = [enrich_metadata(m, tid) for m in metadatas]
        embeddings = self._embed.embed(chunks)
        index = self._get_index()
        vectors = []
        for cid, txt, meta, emb in zip(ids, chunks, enriched, embeddings):
            # Pinecone metadata must be flat JSON-serializable; keep small
            pine_meta = dict(meta)
            pine_meta["content"] = txt
            pine_meta["tenant_id"] = tid
            # Truncate large content for metadata limit (40KB)
            if len(txt) > 8000:
                pine_meta["content"] = txt[:8000]
            vectors.append({"id": cid, "values": emb, "metadata": pine_meta})
        # Batch upsert in 100s
        for i in range(0, len(vectors), 100):
            batch = vectors[i : i + 100]
            index.upsert(vectors=batch, namespace=tid)
        logger.info("Added chunks to Pinecone", count=len(chunks), tenant_id=tid, index=self.index_name)

    def query(self, query_text: str, n_results: int = 5, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        tid = resolve_tenant_id(tenant_id)
        q_emb = self._embed.embed_query(query_text)
        index = self._get_index()
        try:
            resp = index.query(vector=q_emb, top_k=n_results, namespace=tid, include_metadata=True)
            matches = resp.get("matches", []) if isinstance(resp, dict) else getattr(resp, "matches", [])
            docs: List[str] = []
            metas: List[Dict[str, Any]] = []
            distances: List[float] = []
            ids: List[str] = []
            for m in matches:
                if isinstance(m, dict):
                    meta = m.get("metadata") or {}
                    score = m.get("score", 0.0)
                    _id = m.get("id", "")
                else:
                    meta = getattr(m, "metadata", {}) or {}
                    score = getattr(m, "score", 0.0)
                    _id = getattr(m, "id", "")
                content = meta.pop("content", "") if isinstance(meta, dict) else ""
                # score is cosine similarity for pinecone cosine; convert to distance
                distance = 1.0 - float(score)
                docs.append(content)
                metas.append(meta if isinstance(meta, dict) else {})
                distances.append(distance)
                ids.append(_id)
            return {"documents": [docs], "metadatas": [metas], "distances": [distances], "ids": [ids]}
        except Exception as e:
            logger.error("Pinecone query failed", error=str(e))
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}

    def delete_document(self, document_id: str, tenant_id: Optional[str] = None):
        tid = resolve_tenant_id(tenant_id)
        index = self._get_index()
        # Pinecone requires delete by filter — need to fetch ids first via query? Pinecone now supports delete by filter
        try:
            index.delete(filter={"document_id": {"$eq": document_id}}, namespace=tid)
        except Exception:
            # fallback: list + delete ids
            try:
                # No efficient scan; log warning
                logger.warning("Pinecone delete_document via filter failed, may need manual cleanup", document_id=document_id)
            except Exception as e:
                logger.error("Pinecone delete failed", error=str(e))
        logger.info("Deleted document chunks from Pinecone", document_id=document_id, tenant_id=tid)

    def heartbeat(self) -> bool:
        try:
            idx = self._get_index()
            idx.describe_index_stats()
            return True
        except Exception as e:
            logger.warning("Pinecone heartbeat failed", error=str(e))
            return False

    def count(self, tenant_id: Optional[str] = None) -> int:
        try:
            idx = self._get_index()
            tid = resolve_tenant_id(tenant_id)
            stats = idx.describe_index_stats()
            ns = stats.get("namespaces", {}) if isinstance(stats, dict) else getattr(stats, "namespaces", {})
            if tid in ns:
                entry = ns[tid]
                return int(entry.get("vector_count", 0) if isinstance(entry, dict) else getattr(entry, "vector_count", 0))
            return 0
        except Exception:
            return 0
