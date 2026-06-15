import redis.asyncio as redis
import json
from typing import List, Dict
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class SessionMemory:
    def __init__(self):
        self.pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
            max_connections=20,
        )
        self.ttl = 3600  # 1 hour session TTL

    async def get_connection(self) -> redis.Redis:
        """Return a connection from the pool."""
        return redis.Redis(connection_pool=self.pool)

    async def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the session history."""
        key = f"session:{session_id}"
        message = json.dumps({"role": role, "content": content})
        conn = await self.get_connection()
        await conn.rpush(key, message)
        await conn.expire(key, self.ttl)
        logger.info("Added message to session memory", session_id=session_id, role=role)

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve the last N messages from the session history."""
        key = f"session:{session_id}"
        conn = await self.get_connection()
        messages = await conn.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]

    async def clear_session(self, session_id: str):
        """Clear session history."""
        conn = await self.get_connection()
        await conn.delete(f"session:{session_id}")

    async def close(self):
        """Close the connection pool."""
        await self.pool.disconnect()