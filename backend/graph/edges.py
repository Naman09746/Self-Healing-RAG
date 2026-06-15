"""Routing edges — Phase 3B.

Replaces binary should_heal() with 5-way routing:

  SUPPORTED           → output
  PARTIALLY_SUPPORTED → targeted_healing
  UNSUPPORTED         → retrieval_expansion
  CONTRADICTED        → aggressive_rewrite
  no_claims           → aggressive_rewrite (strongest healing)
  max_retries         → output (unconditional)
"""

from typing import Literal
from backend.graph.state import RAGState
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Valid routing destinations
Route = Literal[
    "output",
    "targeted_healing",
    "retrieval_expansion",
    "aggressive_rewrite",
]


def should_heal(state: RAGState) -> Route:
    """Determine routing based on per-claim verdicts (Phase 3B).

    Routing rule priority:
      1. Max retries exhausted → output (unconditional circuit-breaker)
      2. No claims extracted    → aggressive_rewrite
      3. healing_target == "targeted_healing"    → targeted_healing
      4. healing_target == "retrieval_expansion"  → retrieval_expansion
      5. healing_target == "aggressive_rewrite"   → aggressive_rewrite
      6. hallucinated / below-threshold (fallback) → targeted_healing
      7. All good              → output
    """
    # 1. Circuit-breaker — max retries exhausted
    if state.retry_count >= state.max_retries:
        logger.warning(
            "Max retries reached: bailing to output",
            retries=state.retry_count,
            healing_target=state.healing_target,
        )
        return "output"

    # 2. No claims → aggressive rewrite (most severe healing)
    if state.verification_mode == "no_claims":
        logger.info(
            "No claims extracted → aggressive_rewrite",
            retry=state.retry_count,
        )
        return "aggressive_rewrite"

    # 3–5. Route by healing_target (set by Phase 3B critic)
    if state.healing_target == "targeted_healing":
        logger.info(
            "Targeted healing: partial support → targeted healing",
            retry=state.retry_count,
            score=state.grounding_score,
        )
        return "targeted_healing"

    if state.healing_target == "retrieval_expansion":
        logger.info(
            "Retrieval expansion: unsupported claims → expand retrieval",
            retry=state.retry_count,
            score=state.grounding_score,
        )
        return "retrieval_expansion"

    if state.healing_target == "aggressive_rewrite":
        logger.info(
            "Aggressive rewrite: contradicted claims → rewrite query",
            retry=state.retry_count,
            score=state.grounding_score,
        )
        return "aggressive_rewrite"

    # 6. Fallback: hallucinated or below threshold (binary mode compat)
    if state.is_hallucinated or state.grounding_score < settings.GROUNDING_THRESHOLD:
        logger.info(
            "Fallback healing (binary check triggered)",
            retry=state.retry_count,
            score=state.grounding_score,
            hallucinated=state.is_hallucinated,
            healing_target=state.healing_target,
        )
        return "targeted_healing"

    # 7. All good
    return "output"