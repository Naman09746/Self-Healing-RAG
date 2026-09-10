"""BM25 in-memory sparse store — legacy, fast for small corpora, ephemeral."""

from __future__ import annotations

from typing import List, Dict, Optional
import numpy as np
from rank_bm25 import BM25Okapi

from backend.core.logging import get_logger
from backend.storage.tenant import resolve_tenant_id

logger = get_logger(__name__)


class BM25SparseStore:
    """Tenant-aware wrapper around BM25Okapi.

    Stores per-tenant corpus partitions to prevent cross-tenant leakage.
    For backward compatibility, `tenant_id=None` indexes/searches global.
    """

    def __init__(self):
        self._corpora: Dict[str, List[str]] = {}  # tenant_id -> docs
        self._metas: Dict[str, List[Dict]] = {}
        self._bm25: Dict[str, BM25Okapi | None] = {}

    # Compat with old BM25Retriever.index signature (documents, metadata)
    def index(self, documents: List[str], metadata: Optional[List[Dict]] = None, tenant_id: Optional[str] = None) -> None:
        tid = resolve_tenant_id(tenant_id) if tenant_id else "default"
        # If called without tenant_id but metadata contains tenant_id, group by metadata tenant
        if tenant_id is None and metadata and any("tenant_id" in (m or {}) for m in metadata):
            # Group documents by their metadata tenant_id
            by_tenant: Dict[str, tuple[List[str], List[Dict]]] = {}
            for doc, meta in zip(documents, metadata or [{} for _ in documents]):
                t = resolve_tenant_id((meta or {}).get("tenant_id"))
                by_tenant.setdefault(t, ([], []))
                by_tenant[t][0].append(doc)
                by_tenant[t][1].append(meta)
            for t, (docs, metas) in by_tenant.items():
                self._index_for_tenant(t, docs, metas)
            return
        # Single tenant path
        self._index_for_tenant(tid, documents, metadata)

    def _index_for_tenant(self, tid: str, documents: List[str], metadata: Optional[List[Dict]] = None):
        if not documents:
            raise ValueError("Cannot index empty document list")
        if metadata is not None and len(metadata) != len(documents):
            raise ValueError(f"Metadata length {len(metadata)} != documents {len(documents)}")
        try:
            self._corpora[tid] = documents
            self._metas[tid] = metadata or [{} for _ in documents]
            tokenized = [d.lower().split() for d in documents]
            self._bm25[tid] = BM25Okapi(tokenized)
            logger.info("BM25 index rebuilt", tenant_id=tid, document_count=len(documents))
        except Exception as e:
            logger.error("BM25 indexing failed", error=str(e), tenant_id=tid)
            raise

    def retrieve(self, query: str, k: int = 5, tenant_id: Optional[str] = None) -> List[Dict]:
        tid = resolve_tenant_id(tenant_id) if tenant_id else None
        # If no tenant specified, fallback to global search across all tenants (legacy) but filter metadata
        if tid is None:
            # Merge all tenants for backward compat — worst case, but avoids breaking old callers
            # Filter to only include docs where metadata tenant matches if query has tenant hint? No — return empty if not specified?
            # For safety, return from default tenant only
            tid = "default"
        corpus = self._corpora.get(tid, [])
        bm25 = self._bm25.get(tid)
        metas = self._metas.get(tid, [])
        if not bm25 or not corpus:
            return []
        if not query or not query.strip():
            return []
        try:
            tokenized_query = query.lower().split()
            scores = bm25.get_scores(tokenized_query)
            top_n = np.argsort(scores)[::-1][:k]
            results: List[Dict] = []
            for i in top_n:
                if scores[i] > 0:
                    results.append({"content": corpus[i], "metadata": metas[i], "score": float(scores[i]), "chunk_id": metas[i].get("chunk_id", "")})
            return results
        except Exception as e:
            logger.error("BM25 retrieval failed", error=str(e), query=query, tenant_id=tid)
            return []

    def delete_document(self, document_id: str, tenant_id: Optional[str] = None) -> None:
        tid = resolve_tenant_id(tenant_id) if tenant_id else "default"
        corpus = self._corpora.get(tid, [])
        metas = self._metas.get(tid, [])
        if not corpus:
            return
        # Filter out chunks with document_id
        new_docs: List[str] = []
        new_metas: List[Dict] = []
        for doc, meta in zip(corpus, metas):
            if meta.get("document_id") != document_id:
                new_docs.append(doc)
                new_metas.append(meta)
        if len(new_docs) != len(corpus):
            if new_docs:
                self._index_for_tenant(tid, new_docs, new_metas)
            else:
                self._corpora.pop(tid, None)
                self._metas.pop(tid, None)
                self._bm25.pop(tid, None)

    def reset(self) -> None:
        self._corpora.clear()
        self._metas.clear()
        self._bm25.clear()

    def heartbeat(self) -> bool:
        return True

    def count(self, tenant_id: Optional[str] = None) -> int:
        if tenant_id is None:
            return sum(len(v) for v in self._corpora.values())
        tid = resolve_tenant_id(tenant_id)
        return len(self._corpora.get(tid, []))

    # Legacy compat alias
    @property
    def corpus(self) -> List[str]:
        # Return default tenant corpus for legacy callers that accessed bm25_retriever.corpus
        return self._corpora.get("default", [])

    @corpus.setter
    def corpus(self, value: List[str]) -> None:
        self._corpora["default"] = value

    @property
    def metadata(self) -> List[Dict]:
        return self._metas.get("default", [])

    @metadata.setter
    def metadata(self, value: List[Dict]) -> None:
        self._metas["default"] = value

    @property
    def bm25(self) -> Optional[BM25Okapi]:
        return self._bm25.get("default")


# Backward-compat singleton alias
bm25_retriever = BM25SparseStore()
