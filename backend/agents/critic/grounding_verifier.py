"""Per-claim grounding verifier — Phase 3B.

Replaces single-batch LLM call with parallel per-claim verification:
  - Each claim gets its own focused LLM call (better accuracy).
  - asyncio.gather() runs all calls concurrently.
  - Semaphore (max 5) prevents LLM server overload.
  - Returns four verdicts: SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, CONTRADICTED.
"""

import json
import asyncio
from typing import List, Dict, Any
from opentelemetry import trace

from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.agents.generation.llm_client import LLMClient
from backend.agents.critic.verdict import Verdict, ClaimVerdict

logger = get_logger(__name__)

# Maximum concurrent LLM calls — protects Ollama from queue overload and memory spikes
# Increased from 2 to 5 to reduce tail latency for 6-claim verification (3x speedup)
_PARALLELISM = 5
_semaphore = asyncio.Semaphore(_PARALLELISM)

# ── prompt template (one per claim) ─────────────────────────────────────
_VERIFY_CLAIM_PROMPT = """You are a fact-checker. Determine the relationship of the claim below to the source context.

VERDICT OPTIONS (choose exactly one):
  SUPPORTED           — The context directly and clearly supports the claim.
  PARTIALLY_SUPPORTED — The context supports part of the claim, but some elements are missing or nuanced.
  UNSUPPORTED         — The context neither supports nor contradicts the claim (neutral).
  CONTRADICTED        — The context directly contradicts the claim.

SOURCE CONTEXT:
{context}

CLAIM:
{claim}

Respond with a JSON object:
{{"verdict": "<VERDICT>", "reasoning": "<brief explanation>"}}
"""

_VERIFY_CLAIMS_BATCH_PROMPT = """You are a fact-checker. Determine the relationship of each claim below to the source context.

VERDICT OPTIONS (choose exactly one per claim):
  SUPPORTED           — The context directly and clearly supports the claim.
  PARTIALLY_SUPPORTED — The context supports part of the claim, but some elements are missing or nuanced.
  UNSUPPORTED         — The context neither supports nor contradicts the claim (neutral).
  CONTRADICTED        — The context directly contradicts the claim.

SOURCE CONTEXT:
{context}

CLAIMS TO VERIFY:
{claims_formatted}

Respond ONLY with a JSON array of objects with "claim", "verdict", and "reasoning":
[
  {{"claim": "<exact claim text>", "verdict": "SUPPORTED|PARTIALLY_SUPPORTED|UNSUPPORTED|CONTRADICTED", "reasoning": "<brief explanation>"}}
]
"""


class GroundingVerifier:
    """Verifies claims against context chunks using parallel per-claim LLM calls.

    Backward-compatible: verify_claim() and verify_claims_batch() still exist,
    but the primary entry point is verify_claims_parallel().
    """

    def __init__(self, model: str = None):
        self.client = LLMClient(model=model)
        # Instance semaphore allows per-verifier control; falls back to global
        self._semaphore = _semaphore

    # ── parallel entry point (Phase 3B) ──────────────────────────────

    async def verify_claims_parallel(
        self,
        claims: List[str],
        context_chunks: List[str],
    ) -> List[ClaimVerdict]:
        """Verify each claim in a separate async task, with semaphore protection.

        Parameters
        ----------
        claims : list[str]
            Atomic claims extracted from the generated answer.
        context_chunks : list[str]
            Retrieved document chunks to ground against.

        Returns
        -------
        list[ClaimVerdict]
            One verdict per claim, in the same order.
        """
        tracer = get_tracer()
        with tracer.start_as_current_span("grounding_verification") as span:
            span.set_attribute("claims_count", len(claims))
            span.set_attribute("context_chunks", len(context_chunks))

            if not claims:
                span.set_attribute("verdicts_count", 0)
                span.set_status(trace.Status(trace.StatusCode.OK))
                return []

            # Use up to 6 chunks to match generation context (rerank_top_k=6 for k=10)
            context = "\n\n".join(context_chunks[:6])
            span.set_attribute("context_length", len(context))

            # Optimization: for multiple claims, attempt single-call batch verification first
            if len(claims) > 1:
                try:
                    batch_results = await self._verify_claims_batch_fast(claims, context)
                    if batch_results and len(batch_results) == len(claims):
                        span.set_attribute("verification_strategy", "batch_fast")
                        span.set_attribute("verdicts_count", len(batch_results))
                        span.set_attribute("error_count", 0)
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        logger.info("Batch verification completed in single LLM call", claims_count=len(claims))
                        return batch_results
                except Exception as b_err:
                    logger.warning("Batch verification fallback to parallel per-claim", error=str(b_err))

            # Fallback: parallel per-claim execution
            span.set_attribute("verification_strategy", "per_claim_parallel")
            tasks = [
                self._verify_single_claim(claim, context)
                for claim in claims
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            verdicts: List[ClaimVerdict] = []
            error_count = 0
            for claim, result in zip(claims, results):
                if isinstance(result, Exception):
                    error_count += 1
                    logger.warning(
                        "Per-claim verification failed, falling back to UNSUPPORTED",
                        claim=claim[:60],
                        error=str(result),
                    )
                    verdicts.append(ClaimVerdict(
                        claim=claim,
                        verdict=Verdict.UNSUPPORTED,
                        reasoning=f"LLM error: {result}",
                    ))
                else:
                    verdicts.append(result)

            span.set_attribute("verdicts_count", len(verdicts))
            span.set_attribute("error_count", error_count)
            span.set_status(trace.Status(trace.StatusCode.OK))

        return verdicts

    async def _verify_claims_batch_fast(
        self,
        claims: List[str],
        context: str,
    ) -> Optional[List[ClaimVerdict]]:
        """Fast-path: verify all claims in a single structured LLM call."""
        tracer = get_tracer()
        with tracer.start_as_current_span("verify_claims_batch_fast") as span:
            span.set_attribute("claims_count", len(claims))
            claims_formatted = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
            prompt = _VERIFY_CLAIMS_BATCH_PROMPT.format(context=context, claims_formatted=claims_formatted)

            response = await self.client.generate(prompt, format="json")
            start = response.find("[")
            end = response.rfind("]") + 1
            if start < 0 or end <= start:
                return None

            raw_data = json.loads(response[start:end])
            if not isinstance(raw_data, list) or len(raw_data) != len(claims):
                return None

            verdicts: List[ClaimVerdict] = []
            for i, claim in enumerate(claims):
                item = raw_data[i]
                verdict_str = str(item.get("verdict", "UNSUPPORTED")).upper()
                if verdict_str not in {v.value for v in Verdict}:
                    verdict_str = "UNSUPPORTED"
                verdicts.append(
                    ClaimVerdict(
                        claim=claim,
                        verdict=Verdict(verdict_str),
                        reasoning=str(item.get("reasoning", "")),
                    )
                )

            span.set_status(trace.Status(trace.StatusCode.OK))
            return verdicts

    async def _verify_single_claim(
        self,
        claim: str,
        context: str,
    ) -> ClaimVerdict:
        """Verify a single claim against context — wrapped in semaphore."""
        tracer = get_tracer()
        async with self._semaphore:
            with tracer.start_as_current_span("verify_single_claim") as span:
                span.set_attribute("claim", claim[:150])
                span.set_attribute("context_length", len(context))

                prompt = _VERIFY_CLAIM_PROMPT.format(context=context, claim=claim)
                try:
                    response = await self.client.generate(prompt, format="json")
                    parsed = self._parse_verdict(response, claim)
                    span.set_attribute("verdict", parsed.verdict.value)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return parsed
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    logger.error(
                        "Single-claim verification error",
                        claim=claim[:60],
                        error=str(e),
                    )
                    raise

    # ── backward-compatible wrappers ────────────────────────────────

    async def verify_claim(self, claim: str, context_chunks: List[str]) -> Dict[str, Any]:
        """Backward-compatible single-claim verify — returns raw dict."""
        context = "\n\n".join(context_chunks[:6])
        cv = await self._verify_single_claim(claim, context)
        return {"verdict": cv.verdict.value, "reasoning": cv.reasoning}

    async def verify_claims_batch(self, claims: List[str], context_chunks: List[str]) -> List[Dict[str, Any]]:
        """Backward-compatible batch verify — delegates to parallel entry point."""
        # Ensure context truncation consistent with parallel path
        cvs = await self.verify_claims_parallel(claims, context_chunks)
        return [
            {"verdict": cv.verdict.value, "reasoning": cv.reasoning}
            for cv in cvs
        ]

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_verdict(response: str, claim: str) -> ClaimVerdict:
        """Parse LLM JSON response into a ClaimVerdict."""
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            data = json.loads(response[start:end])
            verdict_str = data.get("verdict", "UNSUPPORTED").upper()
            # Validate against known verdicts
            if verdict_str not in {v.value for v in Verdict}:
                logger.warning(
                    "Unknown verdict from LLM, defaulting to UNSUPPORTED",
                    received=verdict_str,
                )
                verdict_str = "UNSUPPORTED"
            return ClaimVerdict(
                claim=claim,
                verdict=Verdict(verdict_str),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(
                "Failed to parse LLM verdict response, defaulting to UNSUPPORTED",
                error=str(e),
                response_snippet=response[:100],
            )
            return ClaimVerdict(
                claim=claim,
                verdict=Verdict.UNSUPPORTED,
                reasoning=f"Parse error: {e}",
            )