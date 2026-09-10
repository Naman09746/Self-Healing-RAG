"""In-memory session store — free-tier fallback, no external dependencies."""

from __future__ import annotations

import json
from typing import List, Dict

from backend.core.logging import get_logger

logger = get_logger(__name__)


class InMemorySessionStore:
    """Pure in-memory session store. Data lost on restart — acceptable for tests."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._store: Dict[str, List[Dict[str, str]]] = {}
        self.pool = None  # compat with health checks that look for pool

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append({"role": role, "content": content})

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        return self._store.get(session_id, [])[-limit:]

    async def clear_session(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    async def close(self) -> None:
        self._store.clear()

    async def heartbeat(self) -> bool:
        return True

    async def get_connection(self):  # compat shim
        raise RuntimeError("InMemorySessionStore has no Redis connection")
