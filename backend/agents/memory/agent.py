from typing import List, Dict, Any
from backend.core.logging import get_logger
from backend.agents.generation.llm_client import LLMClient
from backend.storage.vector.chroma import ChromaStore
import uuid

logger = get_logger(__name__)

class MemoryAgent:
    def __init__(self, model: str = None):
        self.client = LLMClient(model=model)
        self._memory_store = None

    @property
    def memory_store(self):
        if self._memory_store is None:
            self._memory_store = ChromaStore(collection_name="long_term_memory")
        return self._memory_store

    def store_insight(self, query: str, solution: str, metadata: dict = None):
        """Store a successful query-solution pair in long-term memory."""
        doc_id = str(uuid.uuid4())
        content = f"QUERY: {query}\nINSIGHT: {solution}"
        
        props = metadata or {}
        props.update({"type": "insight", "query": query})
        
        self.memory_store.add_chunks([content], [props], [doc_id])
        logger.info("Insight stored in long-term memory", doc_id=doc_id)

    def retrieve_past_insights(self, query: str, k: int = 3) -> List[str]:
        """Retrieve similar past solutions for a new query."""
        try:
            if hasattr(self.memory_store, "collection") and self.memory_store.collection.count() == 0:
                return []
            results = self.memory_store.query(query, n_results=k)
            return results.get("documents", [[]])[0]
        except Exception as e:
            logger.debug("Past insights retrieval skipped or empty", error=str(e))
            return []
