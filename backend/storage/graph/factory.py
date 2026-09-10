"""Factory for GraphStore."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def get_graph_store():
    provider = (getattr(settings, "GRAPH_PROVIDER", "memory") or "memory").lower().strip()
    # Backward compat: if NEO4J_ENABLED=true and provider is memory, escalate to neo4j
    if getattr(settings, "NEO4J_ENABLED", False) and provider == "memory":
        # User explicitly enabled neo4j via flag, respect it
        provider = "neo4j"
    logger.info("Initializing graph store", provider=provider)

    if provider == "neo4j":
        try:
            from backend.storage.graph.neo4j_store import Neo4jGraphStore

            return Neo4jGraphStore()
        except Exception as e:
            logger.error("Failed to init Neo4jGraphStore, falling back to memory", error=str(e))

    if provider == "pg":
        try:
            from backend.storage.graph.pg_graph import PgGraphStore  # type: ignore

            return PgGraphStore()
        except Exception as e:
            logger.warning("PgGraphStore not available, falling back to memory", error=str(e))

    from backend.storage.graph.memory import InMemoryGraphStore

    return InMemoryGraphStore()
