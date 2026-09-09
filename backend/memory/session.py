import redis.asyncio as redis
import json
from typing import List, Dict
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class SessionMemory:
    def __init__(self):
        self.ttl = 3600  # 1 hour session TTL
        self._fallback_memory: Dict[str, List[Dict[str, str]]] = {}
        self.pool = None
        try:
            if getattr(settings, "REDIS_URL", None):
                self.pool = redis.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    max_connections=20,
                )
            else:
                self.pool = redis.ConnectionPool(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    ssl=settings.REDIS_USE_SSL,
                    decode_responses=True,
                    max_connections=20,
                )
        except Exception as e:
            logger.warning("Could not initialize Redis pool for session memory, using in-memory fallback", error=str(e))
            self.pool = None

    async def get_connection(self) -> redis.Redis:
        """Return a connection from the pool."""
        if self.pool is None:
            raise RuntimeError("Redis connection pool is not available")
        return redis.Redis(connection_pool=self.pool)

    async def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the session history."""
        key = f"session:{session_id}"
        message = json.dumps({"role": role, "content": content})
        if self.pool is not None:
            try:
                conn = await self.get_connection()
                await conn.rpush(key, message)
                await conn.expire(key, self.ttl)
                logger.info("Added message to session memory", session_id=session_id, role=role)
                return
            except Exception as e:
                logger.warning("Redis add_message failed, saving to in-memory fallback", error=str(e))

        if session_id not in self._fallback_memory:
            self._fallback_memory[session_id] = []
        self._fallback_memory[session_id].append({"role": role, "content": content})

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve the last N messages from the session history."""
        key = f"session:{session_id}"
        if self.pool is not None:
            try:
                conn = await self.get_connection()
                messages = await conn.lrange(key, -limit, -1)
                if messages:
                    return [json.loads(m) for m in messages]
            except Exception as e:
                logger.warning("Redis get_history failed, reading from in-memory fallback", error=str(e))

        return self._fallback_memory.get(session_id, [])[-limit:]

    async def clear_session(self, session_id: str):
        """Clear session history."""
        if self.pool is not None:
            try:
                conn = await self.get_connection()
                await conn.delete(f"session:{session_id}")
            except Exception:
                pass
        self._fallback_memory.pop(session_id, None)

    async def close(self):
        """Close the connection pool."""
        if self.pool is not None:
            try:
                await self.pool.disconnect()
            except Exception:
                pass