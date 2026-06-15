import asyncio
from sentence_transformers import CrossEncoder
from typing import List, Dict
from opentelemetry import trace
from backend.core.logging import get_logger
from backend.core.observability import get_tracer

logger = get_logger(__name__)


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = None
        self.model_name = model_name
        self._load_lock = asyncio.Lock()

    async def _async_load(self):
        """Thread-safe and non-blocking lazy loading of the reranker model."""
        if self.model is not None:
            return

        async with self._load_lock:
            # Double check to prevent multiple parallel loads
            if self.model is not None:
                return

            try:
                logger.info(f"Loading reranker model: {self.model_name}")
                # Load the model inside a separate thread to prevent blocking event loop
                self.model = await asyncio.to_thread(CrossEncoder, self.model_name)
                logger.info("Reranker model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load reranker: {str(e)}")
                self.model = None

    async def rerank(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        """Async reranking using CrossEncoder in a background thread."""
        tracer = get_tracer()
        with tracer.start_as_current_span("reranking") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("input_documents", len(documents))
            span.set_attribute("top_k", top_k)

            if not documents:
                span.set_attribute("result_count", 0)
                return []

            # Make sure the model is loaded non-blockingly
            await self._async_load()

            if self.model is None:
                logger.warn("Reranker model not loaded, falling back to top_k raw results")
                fallback = documents[:top_k]
                span.set_attribute("result_count", len(fallback))
                span.set_attribute("model_loaded", False)
                return fallback

            span.set_attribute("model_loaded", True)
            span.set_attribute("model_name", self.model_name)

            try:
                pairs = [[query, doc["content"]] for doc in documents]
                # Run heavy CPU predict in a separate thread
                scores = await asyncio.to_thread(self.model.predict, pairs)

                # Copy to avoid mutating original dictionary if they are shared
                result_docs = [dict(doc) for doc in documents]
                for i, score in enumerate(scores):
                    result_docs[i]["rerank_score"] = float(score)

                # Sort by rerank score descending
                reranked = sorted(result_docs, key=lambda x: x["rerank_score"], reverse=True)
                results = reranked[:top_k]

                span.set_attribute("result_count", len(results))
                if results:
                    span.set_attribute("top_score", results[0].get("rerank_score", 0.0))
                span.set_status(trace.Status(trace.StatusCode.OK))

                return results
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error(f"Async rerank failed: {str(e)}, returning raw fallback")
                return documents[:top_k]


reranker = Reranker()
