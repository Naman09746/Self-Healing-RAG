"""Reranker protocol — pluggable."""

from __future__ import annotations

from typing import Protocol, List, Dict, runtime_checkable


@runtime_checkable
class RerankerProtocol(Protocol):
    async def rerank(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        ...

    def heartbeat(self) -> bool:
        ...
