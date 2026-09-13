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
                clean_resp = response.strip()
                # Strip markdown code fences if present
                if "```json" in clean_resp:
                    clean_resp = clean_resp.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in clean_resp:
                    clean_resp = clean_resp.split("```", 1)[1].split("```", 1)[0].strip()

                parsed = None
                try:
                    start = clean_resp.find("[")
                    end = clean_resp.rfind("]") + 1
                    if start >= 0 and end > start:
                        parsed = json.loads(clean_resp[start:end])
                except Exception:
                    pass
                if parsed is None:
                    try:
                        start = clean_resp.find("{")
                        end = clean_resp.rfind("}") + 1
                        if start >= 0 and end > start:
                            parsed = json.loads(clean_resp[start:end])
                    except Exception:
                        pass
                if parsed is None:
                    try:
                        parsed = json.loads(clean_resp)
                    except Exception:
                        parsed = None

                claims: List[str] = []
                if isinstance(parsed, list):
                    claims = [str(c).strip() for c in parsed if str(c).strip()]
                elif isinstance(parsed, dict):
                    for k in ("claims", "facts", "statements", "result", "items", "data"):
                        if k in parsed and isinstance(parsed[k], list):
                            claims = [str(c).strip() for c in parsed[k] if str(c).strip()]
                            break
                    else:
                        claims = [str(v).strip() for v in parsed.values() if isinstance(v, str) and str(v).strip()]

                if not claims:
                    claims = [answer]

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
