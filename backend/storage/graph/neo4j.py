"""Backward-compatible shim — prefer `from backend.storage.graph.factory import get_graph_store`."""

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Keep legacy class alias for imports that do `from backend.storage.graph.neo4j import GraphStore`
try:
    from backend.storage.graph.neo4j_store import Neo4jGraphStore as GraphStore  # noqa: F401
except Exception:
    from backend.storage.graph.memory import InMemoryGraphStore as GraphStore  # type: ignore

# Singleton via factory respecting GRAPH_PROVIDER / NEO4J_ENABLED
try:
    from backend.storage.graph.factory import get_graph_store

    graph_store = get_graph_store()
except Exception as e:
    logger.warning("Could not init graph store via factory, using memory fallback", error=str(e))
    from backend.storage.graph.memory import InMemoryGraphStore

    graph_store = InMemoryGraphStore()  # type: ignore
