"""SessionStore protocol — pluggable session backends."""

from __future__ import annotations

from typing import Protocol, List, Dict, runtime_checkable


@runtime_checkable
class SessionStore(Protocol):
    """Async session store protocol.

    All implementations must handle tenant-agnostic session_id keys
    (caller prefixes with user_uuid as in query.py). Heartbeat is used
    for /health checks.
    """

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        ...

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        ...

    async def clear_session(self, session_id: str) -> None:
        ...

    async def close(self) -> None:
        ...

    async def heartbeat(self) -> bool:
        """Return True if store is reachable. Used for health checks."""
        ...

    # For sync compatibility with legacy SessionMemory.pool checks
    @property
    def pool(self):  # type: ignore[no-untyped-def]
        ...
