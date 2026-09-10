"""Redis-backed session store — Upstash free tier compatible."""

from __future__ import annotations

import json
from typing import List, Dict

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

try:
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore


class RedisSessionStore:
    """Redis session store with TLS/Upstash support and graceful fallback."""

    def __init__(self, ttl: int = 3600, pool_size: int = 20):
        self.ttl = ttl
        self.pool = None
        self._fallback: Dict[str, List[Dict[str, str]]] = {}
        if aioredis is None:
            logger.warning("redis package not available, RedisSessionStore will use in-memory fallback")
            return
        try:
            if getattr(settings, "REDIS_URL", None):
                self.pool = aioredis.ConnectionPool.from_url(
                    settings.REDIS_URL, decode_responses=True, max_connections=pool_size
                )
            else:
                self.pool = aioredis.ConnectionPool(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    ssl=settings.REDIS_USE_SSL,
                    decode_responses=True,
                    max_connections=pool_size,
                )
        except Exception as e:
            logger.warning("Could not init Redis pool, using fallback", error=str(e))
            self.pool = None

    async def get_connection(self):  # type: ignore[no-untyped-def]
        if self.pool is None or aioredis is None:
            raise RuntimeError("Redis pool not available")
        return aioredis.Redis(connection_pool=self.pool)

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        key = f"session:{session_id}"
        message = json.dumps({"role": role, "content": content})
        if self.pool is not None and aioredis is not None:
            try:
                conn = await self.get_connection()
                await conn.rpush(key, message)
                await conn.expire(key, self.ttl)
                return
            except Exception as e:
                logger.warning("Redis add_message failed, fallback", error=str(e))
        # fallback
        self._fallback.setdefault(session_id, []).append({"role": role, "content": content})

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        key = f"session:{session_id}"
        if self.pool is not None and aioredis is not None:
            try:
                conn = await self.get_connection()
                messages = await conn.lrange(key, -limit, -1)
                if messages:
                    return [json.loads(m) for m in messages]
            except Exception as e:
                logger.warning("Redis get_history failed, fallback", error=str(e))
        return self._fallback.get(session_id, [])[-limit:]

    async def clear_session(self, session_id: str) -> None:
        if self.pool is not None and aioredis is not None:
            try:
                conn = await self.get_connection()
                await conn.delete(f"session:{session_id}")
            except Exception:
                pass
        self._fallback.pop(session_id, None)

    async def close(self) -> None:
        if self.pool is not None:
            try:
                await self.pool.disconnect()
            except Exception:
                pass

    async def heartbeat(self) -> bool:
        if self.pool is None or aioredis is None:
            return False
        try:
            conn = await self.get_connection()
            await conn.ping()
            # aioredis may need aclose
            try:
                await conn.aclose()  # type: ignore[attr-defined]
            except Exception:
                try:
                    await conn.close()
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.warning("Redis heartbeat failed", error=str(e))
            return False
