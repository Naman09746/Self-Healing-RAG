"""SessionMemory — backward-compatible shim delegating to pluggable SessionStore factory."""

from __future__ import annotations

import json
from typing import List, Dict, Any

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.memory.store.factory import get_session_store

logger = get_logger(__name__)


class SessionMemory:
    """Backward-compatible SessionMemory that delegates to SESSION_STORE_PROVIDER.

    Supported providers: 'pg' (Postgres, free-tier default), 'redis', 'memory'.
    Original code used Redis directly; this shim keeps attribute `pool` for health checks.
    """

    def __init__(self, provider: str | None = None):
        # Allow explicit override for tests
        if provider is not None:
            # Temporarily patch settings for factory
            orig = getattr(settings, "SESSION_STORE_PROVIDER", "pg")
            try:
                settings.SESSION_STORE_PROVIDER = provider  # type: ignore[attr-defined]
                self._store = get_session_store()
            finally:
                settings.SESSION_STORE_PROVIDER = orig  # type: ignore[attr-defined]
        else:
            self._store = get_session_store()
        # Expose pool for legacy health checks: if pg, this is engine.pool; if redis, it's ConnectionPool; if memory, None
        self.pool = getattr(self._store, "pool", None)
        self.ttl = getattr(settings, "SESSION_TTL", 3600)
        # Keep fallback dict for legacy callers that accessed _fallback_memory directly (tests)
        self._fallback_memory: Dict[str, List[Dict[str, str]]] = getattr(self._store, "_fallback", {}) if hasattr(self._store, "_fallback") else {}

    async def get_connection(self) -> Any:
        # Delegate to store if it has get_connection (redis), else raise
        if hasattr(self._store, "get_connection"):
            return await self._store.get_connection()  # type: ignore[attr-defined]
        raise RuntimeError("Session store has no Redis connection (provider is pg/memory)")

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self._store.add_message(session_id, role, content)

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        return await self._store.get_history(session_id, limit)

    async def clear_session(self, session_id: str) -> None:
        await self._store.clear_session(session_id)

    async def close(self) -> None:
        await self._store.close()

    async def heartbeat(self) -> bool:
        # Used by health checks
        if hasattr(self._store, "heartbeat"):
            try:
                return await self._store.heartbeat()  # type: ignore[attr-defined]
            except Exception:
                return False
        return True