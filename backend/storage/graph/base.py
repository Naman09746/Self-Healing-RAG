"""GraphStore protocol — pluggable knowledge graph backends."""

from __future__ import annotations

from typing import Protocol, List, Dict, Optional, runtime_checkable


@runtime_checkable
class GraphStoreProtocol(Protocol):
    def add_entity(self, name: str, entity_type: str, properties: Optional[Dict] = None) -> None:
        ...

    def add_relationship(self, source_name: str, target_name: str, rel_type: str, properties: Optional[Dict] = None) -> None:
        ...

    def query_graph(self, cypher_query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        ...

    def close(self) -> None:
        ...

    def heartbeat(self) -> bool:
        ...
