"""QdrantStore — Qdrant vector backend."""

from __future__ import annotations

import hashlib
import uuid
from typing import List, Dict, Any, Optional

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.tenant import enrich_metadata, resolve_tenant_id
from backend.storage.vector.embeddings import get_embedding_provider

logger = get_logger(__name__)


class QdrantStore:
    """Tenant-aware Qdrant store using payload filter for isolation."""

    def __init__(self, collection_name: Optional[str] = None, is_cache: bool = False):
        self.collection_name = collection_name or getattr(settings, "QDRANT_COLLECTION_NAME", "rag_collection")
        if is_cache:
            # Cache gets its own collection to avoid mixing cache queries with RAG chunks
            self.collection_name = "query_cache"
        self.dim = getattr(settings, "VECTOR_STORE_DIM", 768)
        self.url = getattr(settings, "QDRANT_URL", "") or "http://localhost:6333"
        self.api_key = getattr(settings, "QDRANT_API_KEY", "") or None
        self._client = None
        self._embed = get_embedding_provider()
        self._ensure_collection_done = False

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, api_key=self.api_key, timeout=10)
            return self._client
        except Exception as e:
            logger.error("Failed to create QdrantClient", error=str(e), url=self.url)
            raise

    def _ensure_collection(self):
        if self._ensure_collection_done:
            return
        client = self._get_client()
        try:
            from qdrant_client.models import Distance, VectorParams

            collections = client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection", collection=self.collection_name, dim=self.dim)
            # Create payload index for tenant_id
            try:
                from qdrant_client.models import PayloadSchemaType

                client.create_payload_index(
                    collection_name=self.collection_name, field_name="tenant_id", field_schema=PayloadSchemaType.KEYWORD
                )
            except Exception:
                pass
            try:
                client.create_payload_index(
                    collection_name=self.collection_name, field_name="document_id", field_schema=PayloadSchemaType.KEYWORD
                )
            except Exception:
                pass
        except Exception as e:
            logger.warning("Qdrant ensure collection failed", error=str(e), collection=self.collection_name)
        finally:
            self._ensure_collection_done = True

    def add_chunks(self, chunks: List[str], metadatas: List[Dict[str, Any]], ids: List[str], tenant_id: Optional[str] = None):
        if not chunks:
            return
        tid = resolve_tenant_id(tenant_id)
        self._ensure_collection()
        if not ids:
            ids = [hashlib.sha256(c.encode("utf-8")).hexdigest()[:48] for c in chunks]
        if metadatas is None:
            metadatas = [{} for _ in chunks]
        enriched = [enrich_metadata(m, tid) for m in metadatas]
        # Attach tenant_id/document_id/chunk_id to payload as top-level for filtering
        for m in enriched:
            m.setdefault("tenant_id", tid)
        embeddings = self._embed.embed(chunks)
        client = self._get_client()
        from qdrant_client.models import PointStruct

        points = []
        for cid, txt, meta, emb in zip(ids, chunks, enriched, embeddings):
            # qdrant requires UUID or int for point id; use deterministic uuid5 from cid
            try:
                point_id = str(uuid.UUID(cid[:32].ljust(32, "0")))
            except Exception:
                # fallback to uuid5
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, cid))
            payload = dict(meta)
            payload["content"] = txt
            payload["chunk_id"] = payload.get("chunk_id", cid)
            payload["id"] = cid
            points.append(PointStruct(id=point_id, vector=emb, payload=payload))
        # Use batch upsert; Qdrant handles 100s efficiently
        client.upsert(collection_name=self.collection_name, points=points)
        logger.info("Added chunks to Qdrant", count=len(chunks), tenant_id=tid, collection=self.collection_name)

    def query(self, query_text: str, n_results: int = 5, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        tid = resolve_tenant_id(tenant_id)
        self._ensure_collection()
        q_emb = self._embed.embed_query(query_text)
        client = self._get_client()
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        q_filter = Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tid))])
        try:
            results = client.search(
                collection_name=self.collection_name,
                query_vector=q_emb,
                query_filter=q_filter,
                limit=n_results,
                with_payload=True,
            )
        except Exception as e:
            # Fallback for new qdrant_client API where method is query_points
            try:
                from qdrant_client.models import Filter as F  # noqa

                results = client.query_points(
                    collection_name=self.collection_name,
                    query=q_emb,
                    query_filter=q_filter,
                    limit=n_results,
                    with_payload=True,
                ).points
            except Exception as e2:
                logger.error("Qdrant query failed", error=str(e), fallback_error=str(e2))
                return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        distances: List[float] = []
        ids: List[str] = []
        for hit in results:
            payload = getattr(hit, "payload", {}) or {}
            content = payload.get("content", "") or payload.get("text", "")
            # Strip content from metadata copy
            meta = {k: v for k, v in payload.items() if k not in ("content", "text")}
            score = getattr(hit, "score", 0.0)  # cosine similarity 0-1
            # Convert cosine similarity to distance for Chroma compatibility (distance = 1 - similarity)
            distance = 1.0 - float(score)
            docs.append(content)
            metas.append(meta)
            distances.append(distance)
            ids.append(payload.get("id", str(hit.id)))
        return {"documents": [docs], "metadatas": [metas], "distances": [distances], "ids": [ids]}

    def delete_document(self, document_id: str, tenant_id: Optional[str] = None):
        tid = resolve_tenant_id(tenant_id)
        self._ensure_collection()
        client = self._get_client()
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        flt = Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tid)), FieldCondition(key="document_id", match=MatchValue(value=document_id))])
        client.delete(collection_name=self.collection_name, points_selector=flt)  # type: ignore[arg-type]
        logger.info("Deleted document chunks from Qdrant", document_id=document_id, tenant_id=tid)

    def heartbeat(self) -> bool:
        try:
            client = self._get_client()
            client.get_collections()
            return True
        except Exception as e:
            logger.warning("Qdrant heartbeat failed", error=str(e))
            return False

    def count(self, tenant_id: Optional[str] = None) -> int:
        try:
            client = self._get_client()
            tid = resolve_tenant_id(tenant_id)
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            flt = Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tid))])
            res = client.count(collection_name=self.collection_name, count_filter=flt, exact=False)
            return int(res.count)
        except Exception:
            return 0
