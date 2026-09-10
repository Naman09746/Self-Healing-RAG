"""Cross-encoder reranker — heavy, for paid tier."""

from __future__ import annotations

import asyncio
from typing import List, Dict

from opentelemetry import trace

from backend.core.logging import get_logger
from backend.core.observability import get_tracer

logger = get_logger(__name__)


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = None
        self.model_name = model_name
        self._load_lock = asyncio.Lock()

    async def _async_load(self):
        if self.model is not None:
            return
        async with self._load_lock:
            if self.model is not None:
                return
            try:
                logger.info(f"Loading reranker model: {self.model_name}")
                from sentence_transformers import CrossEncoder

                self.model = await asyncio.to_thread(CrossEncoder, self.model_name)
                logger.info("Reranker model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load CrossEncoder (fallback to RRF): {str(e)}")
                self.model = None

    async def rerank(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        tracer = get_tracer()
        with tracer.start_as_current_span("reranking") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("input_documents", len(documents))
            span.set_attribute("top_k", top_k)
            if not documents:
                span.set_attribute("result_count", 0)
                return []
            await self._async_load()
            if self.model is None:
                logger.warning("Reranker model not loaded, fallback to top_k")
                span.set_attribute("model_loaded", False)
                return documents[:top_k]
            span.set_attribute("model_loaded", True)
            span.set_attribute("model_name", self.model_name)
            try:
                pairs = [[query, doc["content"]] for doc in documents]
                scores = await asyncio.to_thread(self.model.predict, pairs)
                result_docs = [dict(doc) for doc in documents]
                for i, score in enumerate(scores):
                    result_docs[i]["rerank_score"] = float(score)
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
                logger.error(f"Async rerank failed: {str(e)}, fallback")
                return documents[:top_k]

    def heartbeat(self) -> bool:
        return True
