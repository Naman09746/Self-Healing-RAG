"""PgVectorStore — production pgvector backend.

Stores chunks in Postgres table ``vector_chunks`` with HNSW index.
Tenant isolation via ``WHERE tenant_id = :tid``.

Embedding: delegated to ``EmbeddingProvider`` (Ollama/OpenAI/hash fallback).
This keeps the store agnostic to embedding model and allows offline tests.

Table is created by Alembic migration ``add_vector_chunks_pgvector``; however
this class also lazily ensures the table exists for embedded/Neon setups where
migrations haven't run (best-effort).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.tenant import enrich_metadata, resolve_tenant_id
from backend.storage.vector.embeddings import get_embedding_provider

logger = get_logger(__name__)


def _sync_database_url(url: str) -> str:
    """Convert async URL to sync psycopg URL for sync engine used in health checks if needed."""
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://").replace("postgresql+asyncpg://", "postgresql://")


class PgVectorStore:
    """Tenant-aware pgvector store.

    Args:
        dimension: embedding dimension (defaults to settings.VECTOR_STORE_DIM).
        table: table name.
        ef_search: HNSW ef_search runtime param.
    """

    def __init__(
        self,
        dimension: int | None = None,
        table: str = "vector_chunks",
        ef_search: int | None = None,
        collection_name: str | None = None,  # compat with ChromaStore signature
    ):
        self.dim = dimension or getattr(settings, "VECTOR_STORE_DIM", 768)
        self.table = table
        self.ef_search = ef_search or getattr(settings, "PGVECTOR_EF_SEARCH", 40)
        # collection_name is ignored but accepted for factory parity
        if collection_name:
            logger.info("PgVectorStore ignores collection_name (uses unified table)", collection_name=collection_name)
        self._engine = None
        self._sessionmaker = None
        self._embed = get_embedding_provider()
        self._ensured = False

    def _get_engine(self):
        if self._engine is None:
            # Reuse settings.DATABASE_URL; use async engine
            url = settings.DATABASE_URL
            self._engine = create_async_engine(
                url,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
            self._sessionmaker = sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        return self._engine

    def _get_sessionmaker(self):
        if self._sessionmaker is None:
            self._get_engine()
        return self._sessionmaker

    async def _ensure_table(self):
        if self._ensured:
            return
        # Best-effort create extension + table. Failures are logged but not raised (migration is authoritative).
        try:
            eng = self._get_engine()
            async with eng.begin() as conn:
                # Try to enable pgvector — ignore if not permitted (Neon requires dashboard toggle)
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception as e:
                    logger.warning("Could not CREATE EXTENSION vector (may need manual enable on Neon/RDS)", error=str(e))
                # Create table if not exists with generic vector type
                # Use text column for embedding as fallback if vector type unavailable — handled via try
                await conn.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.table} (
                            id TEXT PRIMARY KEY,
                            tenant_id TEXT NOT NULL,
                            document_id TEXT NOT NULL,
                            chunk_id TEXT NOT NULL,
                            chunk_index INT NOT NULL,
                            content TEXT NOT NULL,
                            embedding vector({self.dim}),
                            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                            created_at TIMESTAMPTZ DEFAULT now()
                        )
                        """
                    )
                )
                # Indexes — best effort
                try:
                    await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_tenant ON {self.table}(tenant_id)"))
                    await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_doc ON {self.table}(document_id)"))
                except Exception as e:
                    logger.warning("Could not create pgvector indexes", error=str(e))
                # HNSW index — may fail if pgvector not enabled or data empty
                try:
                    await conn.execute(
                        text(
                            f"CREATE INDEX IF NOT EXISTS idx_{self.table}_hnsw ON {self.table} USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
                        )
                    )
                except Exception as e:
                    logger.warning("Could not create HNSW index (will use IVFFlat or seq scan)", error=str(e))
        except Exception as e:
            logger.warning("PgVectorStore _ensure_table failed (migration may still be pending)", error=str(e))
        finally:
            self._ensured = True

    # ------------------------------------------------------------------
    # Sync wrappers — ChromaStore is sync; keep same call style for HybridRetriever asyncio.to_thread
    # ------------------------------------------------------------------
    def _run_sync(self, coro):
        """Run an async coro from sync context, handling both no-loop and running-loop cases."""
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        if loop.is_running():
            # Already in a running loop (e.g. IngestionPipeline async context) — offload to a new thread
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return asyncio.run(coro)

    def add_chunks(self, chunks: list[str], metadatas: list[dict[str, Any]], ids: list[str], tenant_id: str | None = None):
        return self._run_sync(self._add_chunks_async(chunks, metadatas, ids, tenant_id))

    async def _add_chunks_async(self, chunks: list[str], metadatas: list[dict[str, Any]], ids: list[str], tenant_id: str | None = None):
        if not chunks:
            return
        tid = resolve_tenant_id(tenant_id)
        await self._ensure_table()
        if not ids:
            ids = [hashlib.sha256(c.encode("utf-8")).hexdigest()[:48] for c in chunks]
        # Pad metadatas if shorter
        if metadatas is None:
            metadatas = [{} for _ in chunks]
        if len(metadatas) < len(chunks):
            metadatas = list(metadatas) + [{} for _ in range(len(chunks) - len(metadatas))]
        enriched = [enrich_metadata(m, tid) for m in metadatas]
        # Compute embeddings
        try:
            embeddings = self._embed.embed(chunks)
        except Exception as e:
            logger.error("Embedding generation failed for pgvector add_chunks", error=str(e))
            raise
        # Validate dim
        if embeddings and len(embeddings[0]) != self.dim:
            logger.warning("Embedding dim mismatch for pgvector", expected=self.dim, got=len(embeddings[0]))
            # If mismatch, we still store but log; truncation/padding could be done but we warn
        sess_maker = self._get_sessionmaker()
        async with sess_maker() as session:
            for i, (content, emb, meta, cid) in enumerate(zip(chunks, embeddings, enriched, ids)):
                document_id = str(meta.get("document_id", ""))
                chunk_index = int(meta.get("chunk_index", i))
                chunk_id = str(meta.get("chunk_id", cid))
                # metadata JSON — ensure serializable
                meta_json = json.dumps(meta, default=str)
                # Store embedding as string "[0.1,0.2,...]" for pgvector
                emb_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
                # Use ON CONFLICT for idempotency
                await session.execute(
                    text(
                        f"""
                        INSERT INTO {self.table} (id, tenant_id, document_id, chunk_id, chunk_index, content, embedding, metadata)
                        VALUES (:id, :tid, :doc_id, :chunk_id, :chunk_index, :content, :embedding::vector, :metadata::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                            tenant_id = EXCLUDED.tenant_id,
                            document_id = EXCLUDED.document_id,
                            chunk_id = EXCLUDED.chunk_id,
                            chunk_index = EXCLUDED.chunk_index,
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """
                    ),
                    {
                        "id": cid,
                        "tid": tid,
                        "doc_id": document_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "content": content,
                        "embedding": emb_str,
                        "metadata": meta_json,
                    },
                )
            await session.commit()
        logger.info("Added chunks to pgvector", count=len(chunks), tenant_id=tid)

    def query(self, query_text: str, n_results: int = 5, tenant_id: str | None = None) -> dict[str, Any]:
        return self._run_sync(self._query_async(query_text, n_results, tenant_id))

    async def _query_async(self, query_text: str, n_results: int = 5, tenant_id: str | None = None) -> dict[str, Any]:
        tid = resolve_tenant_id(tenant_id)
        await self._ensure_table()
        # Embed query
        try:
            q_emb = self._embed.embed_query(query_text)
        except Exception as e:
            logger.error("Embedding generation failed for pgvector query", error=str(e))
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        q_emb_str = "[" + ",".join(str(float(x)) for x in q_emb) + "]"
        sess_maker = self._get_sessionmaker()
        try:
            async with sess_maker() as session:
                # Set ef_search for better recall
                try:
                    await session.execute(text(f"SET hnsw.ef_search = {int(self.ef_search)}"))
                except Exception:
                    pass
                # Cosine distance: embedding <=> query, smaller is more similar. Return 1 - distance as proxy if needed.
                # Use ORDER BY embedding <=> :q_emb
                result = await session.execute(
                    text(
                        f"""
                        SELECT id, content, metadata, embedding <=> :q_emb::vector AS distance
                        FROM {self.table}
                        WHERE tenant_id = :tid
                        ORDER BY embedding <=> :q_emb::vector
                        LIMIT :k
                        """
                    ),
                    {"q_emb": q_emb_str, "tid": tid, "k": n_results},
                )
                rows = result.fetchall()
                docs: list[str] = []
                metas: list[dict[str, Any]] = []
                distances: list[float] = []
                ids: list[str] = []
                for r in rows:
                    _id, content, metadata, distance = r
                    # metadata may be dict or string
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}
                    elif metadata is None:
                        metadata = {}
                    docs.append(content)
                    metas.append(metadata)
                    distances.append(float(distance) if distance is not None else 0.0)
                    ids.append(_id)
                logger.info("pgvector query", query=query_text[:60], n_results=n_results, tenant_id=tid, returned=len(docs))
                return {"documents": [docs], "metadatas": [metas], "distances": [distances], "ids": [ids]}
        except Exception as e:
            logger.error("pgvector query failed", error=str(e), query=query_text[:60])
            # Return empty Chroma-compatible dict on failure to keep HybridRetriever resilient
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}

    def delete_document(self, document_id: str, tenant_id: str | None = None):
        return self._run_sync(self._delete_async(document_id, tenant_id))

    async def _delete_async(self, document_id: str, tenant_id: str | None = None):
        tid = resolve_tenant_id(tenant_id)
        await self._ensure_table()
        sess_maker = self._get_sessionmaker()
        async with sess_maker() as session:
            await session.execute(
                text(f"DELETE FROM {self.table} WHERE document_id = :doc_id AND tenant_id = :tid"),
                {"doc_id": document_id, "tid": tid},
            )
            await session.commit()
        logger.info("Deleted document chunks from pgvector", document_id=document_id, tenant_id=tid)

    def heartbeat(self) -> bool:
        try:
            return self._run_sync(self._heartbeat_async())
        except Exception:
            return False

    async def _heartbeat_async(self) -> bool:
        try:
            await self._ensure_table()
            sess_maker = self._get_sessionmaker()
            async with sess_maker() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning("pgvector heartbeat failed", error=str(e))
            return False

    def count(self, tenant_id: str | None = None) -> int:
        try:
            return self._run_sync(self._count_async(tenant_id))
        except Exception:
            return 0

    async def _count_async(self, tenant_id: str | None = None) -> int:
        tid = resolve_tenant_id(tenant_id)
        await self._ensure_table()
        sess_maker = self._get_sessionmaker()
        async with sess_maker() as session:
            result = await session.execute(
                text(f"SELECT COUNT(*) FROM {self.table} WHERE tenant_id = :tid"), {"tid": tid}
            )
            row = result.fetchone()
            return int(row[0]) if row else 0
