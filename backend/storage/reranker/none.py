"""No-op reranker — free-tier default, no model load."""

from __future__ import annotations

from typing import List, Dict


class NoOpReranker:
    """Returns top_k documents unchanged. Used for RRF-only ranking."""

    def __init__(self, *_, **__):
        self.model = None
        self.model_name = "none"

    async def rerank(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        return documents[:top_k]

    def heartbeat(self) -> bool:
        return True
