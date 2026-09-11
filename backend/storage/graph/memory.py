"""In-memory graph store — free-tier default, no external service."""

from __future__ import annotations

from typing import List, Dict, Optional
from collections import defaultdict

from backend.core.logging import get_logger

logger = get_logger(__name__)


class InMemoryGraphStore:
    """Simple in-memory graph for free-tier / tests.

    Stores entities as dict name-> {type, properties} and edges as list.
    query_graph supports the limited Cypher used by HybridRetriever:
      MATCH (e)-[r]->(related) WHERE toLower(e.name) IN $names RETURN e.name, type(r), related.name
    For other queries returns [].
    """

    def __init__(self):
        self.entities: Dict[str, Dict] = {}
        self.edges: List[Dict] = []
        self._driver = True  # memory store is always available; driver check in retriever allows memory

    def add_entity(self, name: str, entity_type: str, properties: Optional[Dict] = None) -> None:
        if not name:
            return
        # Keep most recent properties, merge
        existing = self.entities.get(name, {})
        self.entities[name] = {"type": entity_type, "properties": {**existing.get("properties", {}), **(properties or {})}}

    def add_relationship(self, source_name: str, target_name: str, rel_type: str, properties: Optional[Dict] = None) -> None:
        if not source_name or not target_name:
            return
        self.edges.append({"source": source_name, "target": target_name, "type": rel_type, "properties": properties or {}})

    def query_graph(self, cypher_query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        if not parameters or "names" not in parameters:
            return []
        names = [str(n).lower() for n in parameters.get("names", [])]
        results: List[Dict] = []
        # Build lookup for fast edge search
        for edge in self.edges:
            src = edge["source"]
            if src.lower() in names:
                results.append({"e.name": src, "type(r)": edge["type"], "related.name": edge["target"]})
                if len(results) >= 15:
                    break
        return results

    def close(self) -> None:
        pass

    def heartbeat(self) -> bool:
        return True
