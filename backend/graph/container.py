"""Service container for dependency management.

Provides a single point of initialization and cleanup for all
application services. This is an intermediate step toward full
dependency injection (FastAPI Depends).

Currently uses lifespan-managed singletons. Each service is created
once during application startup and destroyed during shutdown.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.storage.vector.chroma import ChromaStore
    from backend.storage.retriever import HybridRetriever
    from backend.storage.reranker import Reranker
    from backend.agents.planner.agent import PlannerAgent
    from backend.agents.memory.agent import MemoryAgent
    from backend.agents.generation.agent import GenerationAgent
    from backend.agents.critic.agent import CriticAgent
    from backend.agents.healer.query_rewriter import QueryRewriter
    from backend.agents.evaluation.agent import EvaluationAgent
    from backend.memory.session import SessionMemory
    from backend.memory.query_cache import QueryCache
    from backend.core.telemetry_collector import TelemetryCollector
    from backend.core.config import Settings


class ServiceContainer:
    """Lifespan-managed service container.

    All services are None until the container is initialized.
    Use ``get_container()`` to access the global instance.
    """

    def __init__(self, settings_override: Optional["Settings"] = None) -> None:
        self.settings: Optional["Settings"] = settings_override
        self._initialized: bool = False

        # All services start as None — populated in init()
        self.store: Optional["ChromaStore"] = None
        self.hybrid_retriever: Optional["HybridRetriever"] = None
        self.reranker: Optional["Reranker"] = None
        self.planner: Optional["PlannerAgent"] = None
        self.memory_agent: Optional["MemoryAgent"] = None
        self.generator: Optional["GenerationAgent"] = None
        self.critic: Optional["CriticAgent"] = None
        self.rewriter: Optional["QueryRewriter"] = None
        self.evaluator: Optional["EvaluationAgent"] = None
        self.session_memory: Optional["SessionMemory"] = None
        self.query_cache: Optional["QueryCache"] = None
        self.telemetry_collector: Optional["TelemetryCollector"] = None

    @classmethod
    def build(cls, settings_override: Optional["Settings"] = None) -> "ServiceContainer":
        """Build and initialize an isolated ServiceContainer instance."""
        container = cls(settings_override=settings_override)
        container.init()
        return container

    def init(self) -> None:
        """Initialize all services. Called once during app lifespan startup."""
        if self._initialized:
            return

        from backend.storage.vector.chroma import ChromaStore
        from backend.storage.retriever import HybridRetriever
        from backend.storage.reranker import reranker
        from backend.agents.planner.agent import PlannerAgent
        from backend.agents.memory.agent import MemoryAgent
        from backend.agents.generation.agent import GenerationAgent
        from backend.agents.critic.agent import CriticAgent
        from backend.agents.healer.query_rewriter import QueryRewriter
        from backend.agents.evaluation.agent import EvaluationAgent
        from backend.memory.session import SessionMemory
        from backend.memory.query_cache import QueryCache
        from backend.core.telemetry_collector import telemetry_collector

        col_name = self.settings.CHROMA_COLLECTION_NAME if self.settings else None
        self.store = ChromaStore(collection_name=col_name) if col_name else ChromaStore()
        self.hybrid_retriever = HybridRetriever(self.store)
        self.reranker = reranker
        self.planner = PlannerAgent()
        self.memory_agent = MemoryAgent()
        self.generator = GenerationAgent()
        self.critic = CriticAgent()
        self.rewriter = QueryRewriter()
        self.evaluator = EvaluationAgent()
        self.session_memory = SessionMemory()
        self.query_cache = QueryCache()
        self.telemetry_collector = telemetry_collector

        self._initialized = True

    async def close(self) -> None:
        """Clean up all services. Called during app lifespan shutdown."""
        if not self._initialized:
            return

        if self.session_memory is not None:
            try:
                await self.session_memory.close()
            except Exception:
                pass

        self._initialized = False


# Global container — the single source of truth for all services.
# Usage: ``from backend.graph.container import svc``
svc = ServiceContainer()