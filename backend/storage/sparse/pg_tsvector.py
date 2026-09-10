"""Postgres tsvector sparse store — free-tier persistent, tenant-isolated."""

from __future__ import annotations

import json
from typing import List, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.tenant import resolve_tenant_id

logger = get_logger(__name__)


class PgTsvectorSparseStore:
    """Postgres-backed sparse retrieval using tsvector + ts_rank.

    Table: sparse_chunks (id TEXT PK, tenant_id, document_id, chunk_id, chunk_index, content, content_tsv tsvector, metadata JSONB)
    """

    def __init__(self, table: str = "sparse_chunks"):
        self.table = table
        self._engine = None
        self._maker = None
        self._ensured = False

    def _engine_maker(self):
        if self._engine is None:
            url = settings.DATABASE_URL
            self._engine = create_async_engine(url, echo=False, pool_size=5, max_overflow=10, pool_pre_ping=True)
            self._maker = sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        return self._engine, self._maker

    async def _ensure_table(self):
        if self._ensured:
            return
        try:
            engine, _ = self._engine_maker()
            async with engine.begin() as conn:
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
                            content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
                            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                            created_at TIMESTAMPTZ DEFAULT now()
                        )
                        """
                    )
                )
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_tenant ON {self.table}(tenant_id)"))
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_doc ON {self.table}(document_id)"))
                # GIN index for tsvector
                try:
                    await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_tsv ON {self.table} USING GIN (content_tsv)"))
                except Exception as e:
                    logger.warning("Could not create GIN index", error=str(e))
        except Exception as e:
            # Fallback without generated column (for older Postgres without STORED)
            try:
                engine, _ = self._engine_maker()
                async with engine.begin() as conn:
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
                                content_tsv tsvector,
                                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                                created_at TIMESTAMPTZ DEFAULT now()
                            )
                            """
                        )
                    )
                    await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_tsv ON {self.table} USING GIN (content_tsv)"))
            except Exception as e2:
                logger.warning("PgSparse ensure table failed", error=str(e), fallback_error=str(e2))
        finally:
            self._ensured = True

    def _run_sync(self, coro):
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def index(self, documents: List[str], metadata: Optional[List[Dict]] = None, tenant_id: Optional[str] = None) -> None:
        return self._run_sync(self._index_async(documents, metadata, tenant_id))

    async def _index_async(self, documents: List[str], metadata: Optional[List[Dict]] = None, tenant_id: Optional[str] = None) -> None:
        if not documents:
            return
        await self._ensure_table()
        if metadata is None:
            metadata = [{} for _ in documents]
        # If tenant_id not given but metadata has it, group by metadata tenant
        engine, maker = self._engine_maker()
        assert maker is not None
        async with maker() as session:
            for doc, meta in zip(documents, metadata):
                tid = resolve_tenant_id(tenant_id or (meta or {}).get("tenant_id"))
                doc_id = str(meta.get("document_id", ""))
                chunk_id = str(meta.get("chunk_id", ""))
                chunk_idx = int(meta.get("chunk_index", 0))
                meta_json = json.dumps(meta, default=str)
                # Upsert; for generated tsv column we don't insert content_tsv; for fallback we compute
                try:
                    await session.execute(
                        text(
                            f"""
                            INSERT INTO {self.table} (id, tenant_id, document_id, chunk_id, chunk_index, content, metadata)
                            VALUES (:id, :tid, :doc_id, :chunk_id, :chunk_idx, :content, :metadata::jsonb)
                            ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
                            """
                        ),
                        {"id": chunk_id or doc[:48], "tid": tid, "doc_id": doc_id, "chunk_id": chunk_id, "chunk_idx": chunk_idx, "content": doc, "metadata": meta_json},
                    )
                except Exception as e:
                    # Try with content_tsv explicit for fallback table
                    try:
                        await session.execute(
                            text(
                                f"""
                                INSERT INTO {self.table} (id, tenant_id, document_id, chunk_id, chunk_index, content, content_tsv, metadata)
                                VALUES (:id, :tid, :doc_id, :chunk_id, :chunk_idx, :content, to_tsvector('english', :content), :metadata::jsonb)
                                ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, content_tsv = to_tsvector('english', :content), metadata = EXCLUDED.metadata
                                """
                            ),
                            {"id": chunk_id or doc[:48], "tid": tid, "doc_id": doc_id, "chunk_id": chunk_id, "chunk_idx": chunk_idx, "content": doc, "metadata": meta_json},
                        )
                    except Exception as e2:
                        logger.warning("PgSparse index insert failed", error=str(e), fallback_error=str(e2))
            await session.commit()

    def retrieve(self, query: str, k: int = 5, tenant_id: Optional[str] = None) -> List[Dict]:
        return self._run_sync(self._retrieve_async(query, k, tenant_id))

    async def _retrieve_async(self, query: str, k: int = 5, tenant_id: Optional[str] = None) -> List[Dict]:
        if not query or not query.strip():
            return []
        tid = resolve_tenant_id(tenant_id) if tenant_id else resolve_tenant_id("default")
        await self._ensure_table()
        try:
            _, maker = self._engine_maker()
            assert maker is not None
            async with maker() as session:
                # Try tsvector retrieval with ts_rank
                result = await session.execute(
                    text(
                        f"""
                        SELECT content, metadata, chunk_id, ts_rank(content_tsv, plainto_tsquery('english', :q)) AS score
                        FROM {self.table}
                        WHERE tenant_id = :tid AND content_tsv @@ plainto_tsquery('english', :q)
                        ORDER BY score DESC
                        LIMIT :k
                        """
                    ),
                    {"q": query, "tid": tid, "k": k},
                )
                rows = result.fetchall()
                results: List[Dict] = []
                for content, metadata, chunk_id, score in rows:
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}
                    results.append({"content": content, "metadata": metadata or {}, "score": float(score) if score else 0.0, "chunk_id": chunk_id})
                if results:
                    return results
                # Fallback: LIKE search for small tables or no tsv match
                result2 = await session.execute(
                    text(f"SELECT content, metadata, chunk_id FROM {self.table} WHERE tenant_id = :tid AND content ILIKE :like LIMIT :k"),
                    {"tid": tid, "like": f"%{query.split()[0]}%", "k": k},
                )
                rows2 = result2.fetchall()
                return [{"content": r[0], "metadata": r[1] if isinstance(r[1], dict) else json.loads(r[1] or "{}"), "score": 0.5, "chunk_id": r[2]} for r in rows2]
        except Exception as e:
            logger.warning("PgSparse retrieve failed, fallback to empty", error=str(e), tenant_id=tid)
            return []

    def delete_document(self, document_id: str, tenant_id: Optional[str] = None) -> None:
        return self._run_sync(self._delete_async(document_id, tenant_id))

    async def _delete_async(self, document_id: str, tenant_id: Optional[str] = None) -> None:
        tid = resolve_tenant_id(tenant_id) if tenant_id else resolve_tenant_id("default")
        await self._ensure_table()
        _, maker = self._engine_maker()
        assert maker is not None
        async with maker() as session:
            await session.execute(text(f"DELETE FROM {self.table} WHERE document_id = :did AND tenant_id = :tid"), {"did": document_id, "tid": tid})
            await session.commit()

    def reset(self) -> None:
        self._run_sync(self._reset_async())

    async def _reset_async(self) -> None:
        await self._ensure_table()
        _, maker = self._engine_maker()
        assert maker is not None
        async with maker() as session:
            await session.execute(text(f"DELETE FROM {self.table}"))
            await session.commit()

    def heartbeat(self) -> bool:
        try:
            return self._run_sync(self._heartbeat_async())
        except Exception:
            return False

    async def _heartbeat_async(self) -> bool:
        try:
            await self._ensure_table()
            _, maker = self._engine_maker()
            assert maker is not None
            async with maker() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning("PgSparse heartbeat failed", error=str(e))
            return False

    def count(self, tenant_id: Optional[str] = None) -> int:
        try:
            return self._run_sync(self._count_async(tenant_id))
        except Exception:
            return 0

    async def _count_async(self, tenant_id: Optional[str] = None) -> int:
        tid = resolve_tenant_id(tenant_id) if tenant_id else None
        await self._ensure_table()
        _, maker = self._engine_maker()
        assert maker is not None
        async with maker() as session:
            if tid:
                r = await session.execute(text(f"SELECT COUNT(*) FROM {self.table} WHERE tenant_id = :tid"), {"tid": tid})
            else:
                r = await session.execute(text(f"SELECT COUNT(*) FROM {self.table}"))
            row = r.fetchone()
            return int(row[0]) if row else 0
