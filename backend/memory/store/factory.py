"""Factory for SessionStore."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.memory.store.base import SessionStore

logger = get_logger(__name__)


def get_session_store() -> SessionStore:
    provider = (getattr(settings, "SESSION_STORE_PROVIDER", "pg") or "pg").lower().strip()
    ttl = getattr(settings, "SESSION_TTL", 3600)
    pool_size = getattr(settings, "SESSION_POOL_SIZE", 20)
    logger.info("Initializing session store", provider=provider)

    if provider == "redis":
        try:
            from backend.memory.store.redis_store import RedisSessionStore

            store = RedisSessionStore(ttl=ttl, pool_size=pool_size)
            # If pool failed but fallback will still work, return it; heartbeat will tell
            return store  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to init RedisSessionStore, falling back to pg", error=str(e))

    if provider == "pg":
        try:
            from backend.memory.store.pg_store import PgSessionStore

            return PgSessionStore(ttl=ttl)  # type: ignore[return-value]
        except Exception as e:
            logger.error("Failed to init PgSessionStore, falling back to memory", error=str(e))

    # memory / fallback
    from backend.memory.store.memory import InMemorySessionStore

    return InMemorySessionStore(ttl=ttl)  # type: ignore[return-value]
