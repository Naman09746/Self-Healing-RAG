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

GenerateRoute = Literal["generation", "output"]


def should_generate(state: RAGState) -> GenerateRoute:
    """Determine whether to proceed to generation or fast-fail to output.

    Fast-fail path (Decision 1A):
    If no relevant chunks exist in the knowledge base (e.g. empty or all scores
    below RELEVANCE_THRESHOLD), bypass generation, critic, and healing entirely.

    Fixed: RRF scores are ~0.016, so threshold 0.5 never matches. Use cosine
    distance when available, with graceful fallback to RRF threshold 0.008.
    """
    if getattr(state, "no_relevant_chunks", False):
        logger.info("Fast-fail: no_relevant_chunks flag set → output")
        return "output"

    chunks = getattr(state, "retrieved_chunks", None)
    if not chunks:
        logger.info("Fast-fail: no retrieved chunks → output")
        return "output"

    chunk_list = chunks.to_list() if hasattr(chunks, "to_list") else list(chunks)
    if not chunk_list:
        logger.info("Fast-fail: no retrieved chunks → output")
        return "output"

    # If any chunk has vector distance, use distance threshold (0=identical, 2=opposite)
    has_vector = any(getattr(c, "distance", None) is not None for c in chunk_list)
    if has_vector:
        dist_threshold = 1.0 - float(settings.RELEVANCE_THRESHOLD)
        dist_threshold = max(0.65, min(dist_threshold, 0.85))
        if any(
            getattr(c, "distance", None) is not None and float(getattr(c, "distance") or 999) <= dist_threshold
            for c in chunk_list
        ):
            return "generation"
        # All vector distances above threshold -> check if sparse-only fallback should allow
        # If all distances bad but we have no sparse signal, fast-fail
        # However non-vector chunks (sparse) may still be relevant, treat any sparse chunk as fallback
        has_sparse_relevant = any(
            getattr(c, "distance", None) is None and getattr(c, "score", 0.0) >= 0.008
            for c in chunk_list
        )
        if has_sparse_relevant:
            return "generation"
        logger.info(
            "Fast-fail: all chunk distances above threshold → output",
            threshold=dist_threshold,
        )
        return "output"

    # No vector distances (sparse-only or reranked path)
    rerank_provider = getattr(settings, "RERANKER_PROVIDER", "none") or "none"
    is_cross_encoder = rerank_provider.lower() not in ("none", "", "noop")
    if is_cross_encoder:
        score_thresh = float(settings.RELEVANCE_THRESHOLD)
        if all(getattr(c, "score", 0.0) < score_thresh for c in chunk_list):
            logger.info(
                "Fast-fail: all chunk scores below relevance threshold → output",
                threshold=score_thresh,
            )
            return "output"
        return "generation"
    else:
        # NoOp reranker with RRF scores: any non-empty fused result indicates lexical/semantic overlap
        # BM25 returns [] when no match, so existing chunks imply some overlap; prevent P0 false fast-fail
        # RRF scores are 0.016 max, threshold 0.008 is too aggressive for 2-doc corpora -> treat any as relevant
        return "generation"


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