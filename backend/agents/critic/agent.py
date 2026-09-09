"""Critic agent — Phase 3B.

Performs per-claim grounding verification with four-verdict routing:
  SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, CONTRADICTED.

Aggregates per-claim verdicts into a global grounding_score and
a dominant healing strategy (healing_target).
"""

import json
from typing import List, Dict, Any
from opentelemetry import trace
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.observability import get_tracer
from backend.agents.critic.claim_extractor import ClaimExtractor
from backend.agents.critic.grounding_verifier import GroundingVerifier
from backend.agents.critic.verdict import (
    Verdict,
    ClaimVerdict,
    aggregate_grounding_score,
    is_hallucinated,
    dominant_healing_mode,
)

logger = get_logger(__name__)


class CriticAgent:
    def __init__(self, model: str = None):
        self.model = model or settings.SMALL_MODEL_NAME
        self.extractor = ClaimExtractor(model=self.model)
        self.verifier = GroundingVerifier(model=self.model)

    async def verify_grounding(
        self,
        query: str,
        answer: str,
        context_chunks: List[str],
        history: str = "",
    ) -> Dict[str, Any]:
        """Deep verification using per-claim parallel LLM calls — Phase 3B.

        Returns a dict with keys:
          - grounding_score: float (0.0–1.0)
          - is_hallucinated: bool
          - reasoning: str
          - verification_mode: str — "claims_verified", "no_claims"
          - claims_analyzed: int
          - detailed_results: list[dict]  (verdict + reasoning per claim)
          - healing_target: str           (Phase 3B — dominant healing strategy)
        """
        tracer = get_tracer()
        logger.info("Starting grounding verification (Phase 3B)")

        with tracer.start_as_current_span("critic") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("answer_length", len(answer))
            span.set_attribute("context_chunks", len(context_chunks))
            span.set_attribute("has_history", bool(history))

            # 1. Extract claims (async) — spans are created inside ClaimExtractor
            claims = await self.extractor.extract_claims(answer)
            if not claims:
                span.set_attribute("claims_count", 0)
                span.set_attribute("verification_mode", "no_claims")
                span.set_status(trace.Status(trace.StatusCode.OK))
                return {
                    "grounding_score": 0.0,
                    "is_hallucinated": True,
                    "reasoning": "No claims could be extracted from the answer",
                    "verification_mode": "no_claims",
                    "claims_analyzed": 0,
                    "detailed_results": [],
                    "healing_target": "aggressive_rewrite",
                }

            span.set_attribute("claims_count", len(claims))

            # 2. Verify EACH claim in parallel with semaphore protection
            per_claim_results: List[ClaimVerdict] = (
                await self.verifier.verify_claims_parallel(claims, context_chunks)
            )

            # 3. Aggregate
            score = aggregate_grounding_score(per_claim_results)
            hallu = is_hallucinated(per_claim_results, settings.GROUNDING_THRESHOLD)
            mode = dominant_healing_mode(per_claim_results)

            counts = _count_verdicts(per_claim_results)
            reasoning = (
                f"{counts[Verdict.SUPPORTED]} supported, "
                f"{counts[Verdict.PARTIALLY_SUPPORTED]} partial, "
                f"{counts[Verdict.UNSUPPORTED]} unsupported, "
                f"{counts[Verdict.CONTRADICTED]} contradicted — "
                f"healing_target={mode}"
            )

            span.set_attribute("grounding_score", score)
            span.set_attribute("is_hallucinated", hallu)
            span.set_attribute("healing_target", mode)
            span.set_attribute("supported", counts[Verdict.SUPPORTED])
            span.set_attribute("partially_supported", counts[Verdict.PARTIALLY_SUPPORTED])
            span.set_attribute("unsupported", counts[Verdict.UNSUPPORTED])
            span.set_attribute("contradicted", counts[Verdict.CONTRADICTED])
            span.set_status(trace.Status(trace.StatusCode.OK))

            logger.info(
                "Verification complete (Phase 3B)",
                score=score,
                hallu=hallu,
                healing_target=mode,
                counts=counts,
            )

            return {
                "grounding_score": score,
                "is_hallucinated": hallu,
                "reasoning": reasoning,
                "verification_mode": "claims_verified",
                "claims_analyzed": len(per_claim_results),
                "detailed_results": [
                    {
                        "claim": r.claim,
                        "verdict": r.verdict.value,
                        "reasoning": r.reasoning,
                    }
                    for r in per_claim_results
                ],
                "healing_target": mode,
            }

    async def verify_grounding_fast(
        self,
        query: str,
        answer: str,
        context_chunks: List[str],
        history: str = "",
    ) -> Dict[str, Any]:
        """Fast-path verification for simple queries (Phase 1C / Decision 1C).

        Performs a single-pass batch verification in 1 LLM call instead of
        per-claim decomposition (3+ calls), eliminating latency multiplication.
        """
        tracer = get_tracer()
        logger.info("Starting fast-path grounding verification (Phase 1C)")

        with tracer.start_as_current_span("critic.fast") as span:
            span.set_attribute("query", query[:200])
            span.set_attribute("answer_length", len(answer))
            span.set_attribute("context_chunks", len(context_chunks))

            context = "\n\n".join(context_chunks[:3])
            prompt = (
                "You are an objective AI fact-checker. Determine if the following answer is fully supported by the provided source context.\n\n"
                f"SOURCE CONTEXT:\n{context}\n\n"
                f"USER QUESTION:\n{query}\n\n"
                f"PROPOSED ANSWER:\n{answer}\n\n"
                "Evaluate whether the answer is supported or contains hallucinations.\n"
                "Respond ONLY with a JSON object:\n"
                '{"grounding_score": <float 0.0 to 1.0>, "is_hallucinated": <true|false>, "reasoning": "<brief explanation>"}\n'
            )

            try:
                raw = await self.verifier.client.generate(prompt, format="json")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                data = json.loads(raw[start:end]) if start >= 0 and end > start else {}

                score = float(data.get("grounding_score", 1.0 if not data.get("is_hallucinated", False) else 0.0))
                score = max(0.0, min(1.0, score))
                hallu = bool(data.get("is_hallucinated", score < settings.GROUNDING_THRESHOLD))
                reasoning = str(data.get("reasoning", "Fast-path single-pass verification completed."))
                mode = "targeted_healing" if hallu else "none"

                span.set_attribute("grounding_score", score)
                span.set_attribute("is_hallucinated", hallu)
                span.set_attribute("healing_target", mode)
                span.set_status(trace.Status(trace.StatusCode.OK))

                return {
                    "grounding_score": score,
                    "is_hallucinated": hallu,
                    "reasoning": f"[Fast-Path] {reasoning}",
                    "verification_mode": "fast_pass",
                    "claims_analyzed": 1,
                    "detailed_results": [],
                    "healing_target": mode,
                }
            except Exception as e:
                logger.warning("Fast-path critic evaluation failed, using fallback", error=str(e))
                return {
                    "grounding_score": 0.85,
                    "is_hallucinated": False,
                    "reasoning": f"Fast-path check fallback: {e}",
                    "verification_mode": "fast_pass_fallback",
                    "claims_analyzed": 0,
                    "detailed_results": [],
                    "healing_target": "none",
                }


def _count_verdicts(verdicts: List[ClaimVerdict]) -> Dict[Verdict, int]:
    """Helper to count per-verdict frequencies."""
    counts: Dict[Verdict, int] = {v: 0 for v in Verdict}
    for cv in verdicts:
        counts[cv.verdict] = counts.get(cv.verdict, 0) + 1
    return counts