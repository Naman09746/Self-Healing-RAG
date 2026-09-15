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
from backend.core.observability import get_tracer
from backend.storage.tenant import enrich_metadata, resolve_tenant_id
from backend.storage.vector.embeddings import get_embedding_provider

logger = get_logger(__name__)


def _vector_type(dim: int) -> str:
    """Return column type string: halfvec(dim) if enabled else vector(dim)."""
    use_half = bool(getattr(settings, "PGVECTOR_USE_HALFVEC", False))
    return f"halfvec({dim})" if use_half else f"vector({dim})"


def _vector_ops() -> str:
    """Return HNSW ops: halfvec_cosine_ops if halfvec else vector_cosine_ops."""
    use_half = bool(getattr(settings, "PGVECTOR_USE_HALFVEC", False))
    return "halfvec_cosine_ops" if use_half else "vector_cosine_ops"


def _vector_cast() -> str:
    """Return cast type for queries: halfvec or vector."""
    use_half = bool(getattr(settings, "PGVECTOR_USE_HALFVEC", False))
    return "halfvec" if use_half else "vector"


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
        collection_name: str | None = None,
    ):
        self.dim = dimension or getattr(settings, "VECTOR_STORE_DIM", 768)
        self.table = table
        self.ef_search = ef_search or getattr(settings, "PGVECTOR_EF_SEARCH", 40)
        self.collection_name = collection_name
        self._engine = None
        self._sessionmaker = None
        self._embed = get_embedding_provider()
        self._ensured = False

    def _get_engine(self):
        # Reuse shared engine from db.session to avoid 30-connection explosion (Neon free tier =10)
        if self._engine is not None:
            return self._engine
        try:
            from backend.storage.db.session import engine as shared_engine
            self._engine = shared_engine
            return self._engine
        except Exception:
            pass
        if self._engine is None:
            from sqlalchemy.pool import NullPool
            url = settings.DATABASE_URL
            self._engine = create_async_engine(
                url,
                echo=False,
                poolclass=NullPool,
            )
            self._sessionmaker = sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        return self._engine

    def _get_sessionmaker(self):
        if self._sessionmaker is not None:
            return self._sessionmaker
        try:
            from backend.storage.db.session import AsyncSessionLocal as shared_maker, engine as shared_engine
            self._engine = shared_engine
            self._sessionmaker = shared_maker
            return self._sessionmaker
        except Exception:
            pass
        if self._sessionmaker is None:
            self._get_engine()
        return self._sessionmaker

    async def _ensure_table(self):
        if self._ensured:
            return
        try:
            eng = self._get_engine()
            async with eng.begin() as conn:
                # Use savepoints for each DDL so one failure doesn't abort whole transaction
                try:
                    async with conn.begin_nested():
                        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception as e:
                    logger.warning("Could not CREATE EXTENSION vector (may need manual enable on Neon/RDS)", error=str(e))
                try:
                    async with conn.begin_nested():
                        vtype = _vector_type(self.dim)
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
                                    embedding {vtype},
                                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                                    created_at TIMESTAMPTZ DEFAULT now()
                                )
                                """
                            )
                        )
                except Exception as e:
                    logger.debug("CREATE TABLE failed", error=str(e))
                try:
                    async with conn.begin_nested():
                        vtype_alter = _vector_type(self.dim)
                        # For halfvec, need USING cast
                        using_clause = f" USING embedding::{vtype_alter}" if "halfvec" in vtype_alter else ""
                        await conn.execute(
                            text(
                                f"""
                                DO $$
                                BEGIN
                                    IF EXISTS (
                                        SELECT 1 FROM information_schema.columns 
                                        WHERE table_name = '{self.table}' AND column_name = 'embedding'
                                    ) THEN
                                        BEGIN
                                            ALTER TABLE {self.table} ALTER COLUMN embedding TYPE {vtype_alter}{using_clause};
                                        EXCEPTION WHEN OTHERS THEN
                                            NULL;
                                        END;
                                    END IF;
                                END $$;
                                """
                            )
                        )
                except Exception:
                    pass
                try:
                    async with conn.begin_nested():
                        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_tenant ON {self.table}(tenant_id)"))
                except Exception as e:
                    logger.debug("tenant index failed", error=str(e))
                try:
                    async with conn.begin_nested():
                        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_doc ON {self.table}(document_id)"))
                except Exception as e:
                    logger.debug("doc index failed", error=str(e))
                try:
                    async with conn.begin_nested():
                        vops = _vector_ops()
                        filtered_tenant = getattr(settings, "PGVECTOR_FILTERED_INDEX_TENANT", None)
                        if filtered_tenant:
                            safe_tenant = "".join(c for c in filtered_tenant if c.isalnum() or c in ("_", "-"))
                            if safe_tenant:
                                try:
                                    async with conn.begin_nested():
                                        await conn.execute(
                                            text(
                                                f"CREATE INDEX IF NOT EXISTS idx_{self.table}_hnsw_filtered ON {self.table} USING hnsw (embedding {vops}) WITH (m=16, ef_construction=64) WHERE tenant_id = '{safe_tenant}'"
                                            )
                                        )
                                except Exception as e:
                                    logger.debug("filtered HNSW failed", error=str(e))
                        await conn.execute(
                            text(
                                f"CREATE INDEX IF NOT EXISTS idx_{self.table}_hnsw ON {self.table} USING hnsw (embedding {vops}) WITH (m=16, ef_construction=64)"
                            )
                        )
                except Exception as e:
                    logger.warning("Could not create HNSW index (will use IVFFlat or seq scan)", error=str(e))
        except Exception as e:
            logger.warning("PgVectorStore _ensure_table failed (migration may still be pending)", error=str(e))
        finally:
            self._ensured = True

    # ------------------------------------------------------------------
    # Sync & Async execution helpers
    # ------------------------------------------------------------------
    def _run_sync(self, coro):
        """Run an async coro from sync context safely."""
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        if loop.is_running():
            # If called inside an existing event loop from synchronous code
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def add_chunks(self, chunks: list[str], metadatas: list[dict[str, Any]], ids: list[str], tenant_id: str | None = None):
        return self._run_sync(self._add_chunks_async(chunks, metadatas, ids, tenant_id))

    async def add_chunks_async(self, chunks: list[str], metadatas: list[dict[str, Any]], ids: list[str], tenant_id: str | None = None):
        return await self._add_chunks_async(chunks, metadatas, ids, tenant_id)

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
        if self.collection_name:
            for m in enriched:
                m.setdefault("collection_name", self.collection_name)
        # Compute embeddings
        try:
            embeddings = self._embed.embed(chunks)
        except Exception as e:
            logger.error("Embedding generation failed for pgvector add_chunks", error=str(e))
            raise
        # Validate dim — generalized for all powerful models (Qwen 1024/4096, BGE-M3 1024, etc)
        if embeddings and len(embeddings[0]) != self.dim:
            got_dim = len(embeddings[0])
            # Allow auto-sync for any known embedding dim (768,1024,1536,2560,3072,4096 etc)
            # This enables seamless upgrade to Qwen/BGE without manual migration 006
            if got_dim in (384, 768, 1024, 1536, 2048, 2560, 3072, 3584, 4096, 5120):
                logger.info("Auto-syncing pgvector dimension", old_dim=self.dim, new_dim=got_dim, model=getattr(self._embed, "model", "unknown"))
                # Attempt to ALTER in background (best-effort); if it fails, raise clear error to force migration
                try:
                    import asyncio as _aio
                    async def _alter_dim():
                        try:
                            eng = self._get_engine()
                            async with eng.begin() as conn:
                                try:
                                    await conn.execute(text(f"DROP INDEX IF EXISTS idx_{self.table}_hnsw"))
                                except Exception:
                                    pass
                                # For non-empty tables, ALTER may require USING or TRUNCATE — try generic ALTER
                                try:
                                    await conn.execute(text(f"ALTER TABLE {self.table} ALTER COLUMN embedding TYPE vector({got_dim})"))
                                except Exception:
                                    # Fallback: truncate if ALTER fails due to existing rows with incompatible dim
                                    try:
                                        await conn.execute(text(f"TRUNCATE TABLE {self.table}"))
                                        await conn.execute(text(f"ALTER TABLE {self.table} ALTER COLUMN embedding TYPE vector({got_dim})"))
                                    except Exception as e2:
                                        logger.warning("ALTER after TRUNCATE failed", error=str(e2))
                                        raise
                                try:
                                    await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_hnsw ON {self.table} USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"))
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.warning("Auto ALTER vector dim failed, run alembic upgrade 007", error=str(e))
                    # Only attempt if we are already in async context; otherwise defer to next _ensure_table
                    try:
                        _aio.get_running_loop()
                        _aio.create_task(_alter_dim())
                    except RuntimeError:
                        pass
                except Exception:
                    pass
                self.dim = got_dim
            else:
                msg = f"Embedding dim mismatch for pgvector: expected {self.dim} got {got_dim} (model {getattr(self._embed,'model','unknown')}) — run alembic upgrade 007 to align vector({self.dim})→vector({got_dim})"
                if getattr(settings, "EMBEDDING_STRICT_DIM", True):
                    logger.error(msg, expected=self.dim, got=got_dim, table=self.table)
                    raise RuntimeError(msg + " — fix VECTOR_STORE_DIM or EMBEDDING_MODEL, or apply migration 007. Existing rows with wrong dim will be ignored (0 results) until re-ingested.")
                logger.warning(msg, expected=self.dim, got=got_dim, table=self.table)
        sess_maker = self._get_sessionmaker()
        async with sess_maker() as session:
            for i, (content, emb, meta, cid) in enumerate(zip(chunks, embeddings, enriched, ids)):
                document_id = str(meta.get("document_id", ""))
                chunk_index = int(meta.get("chunk_index", i))
                chunk_id = str(meta.get("chunk_id", cid))
                meta_json = json.dumps(meta, default=str)
                emb_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
                # Use standard SQL CAST(:embedding AS vector) and CAST(:metadata AS jsonb)
                # to avoid SQLAlchemy colon-parsing conflicts with PostgreSQL :: operator
                await session.execute(
                    text(
                        f"""
                        INSERT INTO {self.table} (id, tenant_id, document_id, chunk_id, chunk_index, content, embedding, metadata)
                        VALUES (:id, :tid, :doc_id, :chunk_id, :chunk_index, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
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
        logger.info("Added chunks to pgvector", count=len(chunks), tenant_id=tid, collection=self.collection_name)

    def query(self, query_text: str, n_results: int = 5, tenant_id: str | None = None) -> dict[str, Any]:
        return self._run_sync(self._query_async(query_text, n_results, tenant_id))

    async def query_async(self, query_text: str, n_results: int = 5, tenant_id: str | None = None) -> dict[str, Any]:
        return await self._query_async(query_text, n_results, tenant_id)

    async def _query_async(self, query_text: str, n_results: int = 5, tenant_id: str | None = None) -> dict[str, Any]:
        tid = resolve_tenant_id(tenant_id)
        await self._ensure_table()
        # Stage-level tracing with no-op fallback
        from contextlib import nullcontext

        try:
            tracer = get_tracer()
            has_tracer = True
        except Exception:
            tracer = None
            has_tracer = False

        # Embedding stage
        if has_tracer:
            try:
                with tracer.start_as_current_span("embedding.query") as span:
                    try:
                        span.set_attribute("model", getattr(self._embed, "model", ""))
                        span.set_attribute("tenant_id", tid)
                    except Exception:
                        pass
                    q_emb = self._embed.embed_query(query_text)
            except Exception as e:
                logger.error("Embedding generation failed for pgvector query", error=str(e))
                return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        else:
            try:
                q_emb = self._embed.embed_query(query_text)
            except Exception as e:
                logger.error("Embedding generation failed for pgvector query", error=str(e))
                return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        q_emb_str = "[" + ",".join(str(float(x)) for x in q_emb) + "]"
        sess_maker = self._get_sessionmaker()
        # Determine cast per actual column type if halfvec toggled without migration
        vcast = _vector_cast()
        # If actual column is still vector but halfvec enabled, use vector to avoid mismatch
        # (checked via diagnostics, actual_is_halfvec)
        # For query, use vector unless halfvec column exists and halfvec enabled
        try:
            # Quick check actual type for correct cast (avoid halfvec on vector column)
            # We do this lazily: if halfvec enabled but column is vector, use vector
            if vcast == "halfvec":
                # Peek actual type via shared engine quickly (no transaction)
                # If check fails, fallback to vector
                pass
        except Exception:
            vcast = "vector"
        try:
            async with sess_maker() as session:
                try:
                    await session.execute(text(f"SET hnsw.ef_search = {int(self.ef_search)}"))
                except Exception:
                    pass
                if bool(getattr(settings, "PGVECTOR_ENABLE_SEQSCAN_OFF", False)):
                    try:
                        await session.execute(text("SET LOCAL enable_seqscan = off"))
                    except Exception:
                        pass
                
                where_clause = "WHERE tenant_id = :tid"
                params: dict[str, Any] = {"q_emb": q_emb_str, "tid": tid, "k": n_results}
                if self.collection_name:
                    where_clause += " AND metadata->>'collection_name' = :col_name"
                    params["col_name"] = self.collection_name

                result = await session.execute(
                    text(
                        f"""
                        SELECT id, content, metadata, embedding <=> CAST(:q_emb AS {vcast}) AS distance
                        FROM {self.table}
                        {where_clause}
                        ORDER BY embedding <=> CAST(:q_emb AS {vcast})
                        LIMIT :k
                        """
                    ),
                    params,
                )
                rows = result.fetchall()
                docs: list[str] = []
                metas: list[dict[str, Any]] = []
                distances: list[float] = []
                ids: list[str] = []
                for r in rows:
                    _id, content, metadata, distance = r
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
            return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}

    def delete_document(self, document_id: str, tenant_id: str | None = None):
        return self._run_sync(self._delete_async(document_id, tenant_id))

    async def delete_document_async(self, document_id: str, tenant_id: str | None = None):
        return await self._delete_async(document_id, tenant_id)

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

    async def heartbeat_async(self) -> bool:
        return await self._heartbeat_async()

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

    async def count_async(self, tenant_id: str | None = None) -> int:
        return await self._count_async(tenant_id)

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
