import json
from typing import List
from opentelemetry import trace
from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.agents.generation.llm_client import LLMClient

logger = get_logger(__name__)


class ClaimExtractor:
    def __init__(self, model: str = None):
        self.client = LLMClient(model=model)

    async def extract_claims(self, answer: str) -> List[str]:
        """Extract atomic factual claims from the answer (async)."""
        tracer = get_tracer()
        with tracer.start_as_current_span("claim_extraction") as span:
            span.set_attribute("answer_length", len(answer))

            prompt = f"""You are a linguistics expert. Extract all individual factual claims from the following text.
A "factual claim" is a simple, atomic statement that can be verified as true or false.

TEXT:
{answer}

Respond ONLY with a JSON list of strings.

CLAIMS:
"""

            try:
                response = await self.client.generate(prompt, format="json")
                claims = json.loads(response)
                span.set_attribute("claims_count", len(claims))
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info("Claims extracted", count=len(claims))
                return claims
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("claims_count", 1)  # fallback
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error("Claim extraction failed", error=str(e))
                return [answer]  # Fallback to whole answer as one claim
