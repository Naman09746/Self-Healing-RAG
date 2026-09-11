"""Postgres-backed session store — free-tier default, reuses DATABASE_URL."""

from __future__ import annotations

import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class PgSessionStore:
    """Postgres session store with single table + JSONB. No extra containers."""

    def __init__(self, ttl: int = 3600, table: str = "session_messages"):
        self.ttl = ttl
        self.table = table
        self.pool = None  # compat; indicates non-Redis but still has DB pool
        self._engine = None
        self._maker = None
        self._ensured = False
        self._fallback: Dict[str, List[Dict[str, str]]] = {}

    def _engine_maker(self):
        if self._engine is None:
            from sqlalchemy.pool import NullPool
            url = settings.DATABASE_URL
            self._engine = create_async_engine(
                url, echo=False, poolclass=NullPool
            )
            self._maker = sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
            # keep pool attribute truthy for health checks
            self.pool = self._engine.pool  # type: ignore[attr-defined]
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
                            id SERIAL PRIMARY KEY,
                            session_id TEXT NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT now(),
                            expires_at TIMESTAMPTZ
                        )
                        """
                    )
                )
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_session ON {self.table}(session_id)"))
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_expires ON {self.table}(expires_at)"))
        except Exception as e:
            logger.warning("PgSessionStore ensure table failed, using fallback", error=str(e))
        finally:
            self._ensured = True

    async def get_connection(self):  # type: ignore[no-untyped-def]
        """Compat shim — returns async session maker; health checks use heartbeat() instead."""
        raise RuntimeError("PgSessionStore uses Postgres, not Redis. Use heartbeat() for health.")

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self._ensure_table()
        try:
            _, maker = self._engine_maker()
            assert maker is not None
            expires = datetime.utcnow() + timedelta(seconds=self.ttl)
            async with maker() as session:
                await session.execute(
                    text(
                        f"INSERT INTO {self.table} (session_id, role, content, expires_at) VALUES (:sid, :role, :content, :exp)"
                    ),
                    {"sid": session_id, "role": role, "content": content, "exp": expires},
                )
                await session.commit()
            # also keep fallback for fast read
            self._fallback.setdefault(session_id, []).append({"role": role, "content": content})
            # trim fallback
            if len(self._fallback[session_id]) > 50:
                self._fallback[session_id] = self._fallback[session_id][-50:]
        except Exception as e:
            logger.warning("Pg add_message failed, fallback", error=str(e))
            self._fallback.setdefault(session_id, []).append({"role": role, "content": content})

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        await self._ensure_table()
        try:
            _, maker = self._engine_maker()
            assert maker is not None
            async with maker() as session:
                result = await session.execute(
                    text(
                        f"""
                        SELECT role, content FROM {self.table}
                        WHERE session_id = :sid
                          AND (expires_at IS NULL OR expires_at > now())
                        ORDER BY created_at ASC
                        LIMIT :lim OFFSET (SELECT GREATEST(0, COUNT(*) - :lim) FROM {self.table} WHERE session_id = :sid)
                        """
                    ),
                    {"sid": session_id, "lim": limit},
                )
                rows = result.fetchall()
                if rows:
                    return [{"role": r[0], "content": r[1]} for r in rows]
                # Try simpler query for Neon compat (no offset subquery issues)
                result2 = await session.execute(
                    text(f"SELECT role, content FROM {self.table} WHERE session_id = :sid ORDER BY id DESC LIMIT :lim"),
                    {"sid": session_id, "lim": limit},
                )
                rows2 = result2.fetchall()
                # reverse to ASC
                return [{"role": r[0], "content": r[1]} for r in reversed(rows2)]
        except Exception as e:
            logger.warning("Pg get_history failed, fallback", error=str(e))
        return self._fallback.get(session_id, [])[-limit:]

    async def clear_session(self, session_id: str) -> None:
        await self._ensure_table()
        try:
            _, maker = self._engine_maker()
            assert maker is not None
            async with maker() as session:
                await session.execute(text(f"DELETE FROM {self.table} WHERE session_id = :sid"), {"sid": session_id})
                await session.commit()
        except Exception:
            pass
        self._fallback.pop(session_id, None)

    async def close(self) -> None:
        if self._engine is not None:
            try:
                await self._engine.dispose()
            except Exception:
                pass

    async def heartbeat(self) -> bool:
        try:
            await self._ensure_table()
            engine, maker = self._engine_maker()
            assert maker is not None
            async with maker() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning("PgSessionStore heartbeat failed", error=str(e))
            return False
