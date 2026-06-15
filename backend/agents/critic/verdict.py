"""Verdict types for per-claim grounding verification — Phase 3B.

Four-verdict system replaces binary supported/hallucinated:
  - SUPPORTED         → direct evidence found in context
  - PARTIALLY_SUPPORTED → partial evidence, missing nuance
  - UNSUPPORTED       → no evidence either way
  - CONTRADICTED      → context directly contradicts the claim
"""

from enum import Enum
from typing import List, Dict
from pydantic import BaseModel


class Verdict(str, Enum):
    """Single-claim verification verdict — serialisable as str."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"

    @property
    def is_positive(self) -> bool:
        return self in (Verdict.SUPPORTED, Verdict.PARTIALLY_SUPPORTED)

    @property
    def is_negative(self) -> bool:
        return self in (Verdict.UNSUPPORTED, Verdict.CONTRADICTED)


class ClaimVerdict(BaseModel):
    """Typed result for a single-claim verification."""
    claim: str
    verdict: Verdict
    reasoning: str


# ── helpers ────────────────────────────────────────────────────────────

VERDICT_WEIGHTS: Dict[Verdict, float] = {
    Verdict.SUPPORTED: 1.0,
    Verdict.PARTIALLY_SUPPORTED: 0.5,
    Verdict.UNSUPPORTED: 0.0,
    Verdict.CONTRADICTED: -0.5,  # worse than unsupported
}

VERDICT_LABELS: Dict[str, str] = {
    "SUPPORTED": "Claim is directly supported by source context.",
    "PARTIALLY_SUPPORTED": "Claim is partially supported — some elements missing or nuanced.",
    "UNSUPPORTED": "No evidence found in source context (neutral).",
    "CONTRADICTED": "Source context directly contradicts the claim.",
}


def aggregate_grounding_score(verdicts: List[ClaimVerdict]) -> float:
    """Aggregate per-claim verdicts into a 0.0–1.0 grounding score.

    SUPPORTED → 1.0, PARTIALLY_SUPPORTED → 0.5,
    UNSUPPORTED → 0.0, CONTRADICTED → -0.5 (clamped to 0).

    Final score = (sum of weights) / total_claims, clamped to [0.0, 1.0].
    """
    if not verdicts:
        return 0.0
    total = sum(max(VERDICT_WEIGHTS.get(v.verdict, 0.0), 0.0) for v in verdicts)
    return min(max(total / len(verdicts), 0.0), 1.0)


def is_hallucinated(verdicts: List[ClaimVerdict], threshold: float = 0.5) -> bool:
    """Returns True if any claim is CONTRADICTED or score below threshold."""
    if not verdicts:
        return True
    if any(v.verdict == Verdict.CONTRADICTED for v in verdicts):
        return True
    return aggregate_grounding_score(verdicts) < threshold


def dominant_healing_mode(verdicts: List[ClaimVerdict]) -> str:
    """Determine the healing strategy from per-claim verdicts.

    Returns one of:
      - "none"                 → SUPPORTED only, or empty
      - "targeted_healing"     → PARTIALLY_SUPPORTED majority or any
      - "retrieval_expansion"  → UNSUPPORTED majority
      - "aggressive_rewrite"   → CONTRADICTED present
    """
    if not verdicts:
        return "none"

    counts = {v: 0 for v in Verdict}
    for cv in verdicts:
        counts[cv.verdict] = counts.get(cv.verdict, 0) + 1

    # Priority: contradicted → unsupported → partially_supported
    if counts.get(Verdict.CONTRADICTED, 0) > 0:
        return "aggressive_rewrite"
    if counts.get(Verdict.UNSUPPORTED, 0) > counts.get(Verdict.SUPPORTED, 0):
        return "retrieval_expansion"
    if counts.get(Verdict.PARTIALLY_SUPPORTED, 0) > 0:
        return "targeted_healing"

    return "none"


__all__ = [
    "Verdict",
    "ClaimVerdict",
    "aggregate_grounding_score",
    "is_hallucinated",
    "dominant_healing_mode",
    "VERDICT_WEIGHTS",
    "VERDICT_LABELS",
]