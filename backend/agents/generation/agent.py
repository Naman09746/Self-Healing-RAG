from typing import List, Dict, Any, AsyncGenerator
from opentelemetry import trace
from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.agents.generation.llm_client import LLMClient

logger = get_logger(__name__)


class GenerationAgent:
    def __init__(self, model: str = None):
        self.client = LLMClient(model=model)

    def _build_prompt(self, query: str, context_chunks: List[str], history: str = "") -> str:
        """Build the prompt template shared by both sync and streaming paths."""
        # Enumerate chunks for citation and truncate to token budget (~3000 tokens ≈ 12000 chars)
        labeled = []
        for i, c in enumerate(context_chunks):
            # Truncate individual chunk to avoid one huge chunk dominating
            trimmed = c[:3000] if len(c) > 3000 else c
            labeled.append(f"[Chunk {i+1}] {trimmed}")
        context = "\n\n".join(labeled)
        # Global budget: ~12000 chars (~3000 tokens) + history + query
        if len(context) > 12000:
            context = context[:12000] + "\n...[truncated]"
        history_section = f"\nCONVERSATION HISTORY:\n{history[:2000]}\n" if history else ""
        return f"""You are a professional assistant. Use ONLY the following retrieved context and conversation history to answer the question.
If the answer is not contained in the context, say you don't know. Do not fabricate information.
Cite sources where possible using [Chunk N] notation.
{history_section}
CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

    async def generate_answer(self, query: str, context_chunks: List[str], history: str = "") -> Dict[str, Any]:
        """Generate an answer based on the provided context and history (async)."""
        tracer = get_tracer()
        with tracer.start_as_current_span("generation") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("context_chunks", len(context_chunks))
            span.set_attribute("has_history", bool(history))

            prompt = self._build_prompt(query, context_chunks, history)
            span.set_attribute("prompt_length", len(prompt))

            response = await self.client.generate(prompt)
            span.set_attribute("answer_length", len(response))
            span.set_status(trace.Status(trace.StatusCode.OK))

            return {
                "answer": response,
                "model": self.client.model,
                "context_used": len(context_chunks),
            }

    async def generate_answer_stream(
        self, query: str, context_chunks: List[str], history: str = ""
    ) -> AsyncGenerator[str, None]:
        """Stream answer tokens one by one.

        Yields:
            Individual decoded tokens as the LLM produces them.
        """
        prompt = self._build_prompt(query, context_chunks, history)
        async for token in self.client.generate_stream(prompt):
            yield token
