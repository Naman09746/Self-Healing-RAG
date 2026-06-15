"""Unit tests for edges.py should_heal() — Phase 3B 4-way routing.

Tests cover:
  - All 5 routing destinations: output, targeted_healing, retrieval_expansion,
    aggressive_rewrite
  - Circuit-breaker when max retries exhausted
  - no_claims verification_mode → aggressive_rewrite
  - healing_target priority over is_hallucinated fallback
  - Legacy binary-mode fallback (healing_target="" + is_hallucinated=True)
"""

import pytest
from backend.graph.state import RAGState, GenerationResult
from backend.graph.edges import should_heal


# ── helpers ──────────────────────────────────────────────────────────────

def _state(**overrides) -> RAGState:
    """Build minimal RAGState with safe defaults."""
    defaults = {
        "query": "test query",
        "retry_count": 0,
        "max_retries": 1,
        "grounding_score": 0.0,
        "is_hallucinated": False,
        "verification_mode": "claims_verified",
        "healing_target": "",
        "generation_result": GenerationResult(
            answer="Some answer.",
            model="test",
        ),
    }
    defaults.update(overrides)
    return RAGState(**defaults)


class TestCircuitBreaker:
    """Rule 1: max retries exhausted → output (unconditional)."""

    def test_max_retries_exhausted_output(self):
        """Even if hallucinated, exhausted retries must go to output."""
        state = _state(
            retry_count=1,
            max_retries=1,
            is_hallucinated=True,
            grounding_score=0.0,
        )
        assert should_heal(state) == "output"

    def test_max_retries_exhausted_no_claims(self):
        """Even with no_claims, exhausted retries must go to output."""
        state = _state(
            retry_count=2,
            max_retries=2,
            verification_mode="no_claims",
            is_hallucinated=True,
        )
        assert should_heal(state) == "output"

    def test_max_retries_not_exhausted_still_checks(self):
        """retry_count < max_retries should not short-circuit."""
        state = _state(
            retry_count=0,
            max_retries=1,
            is_hallucinated=False,
            grounding_score=0.8,
            healing_target="targeted_healing",
        )
        # Should route by healing_target, not circuit-breaker
        assert should_heal(state) == "targeted_healing"


class TestNoClaimsRouting:
    """Rule 2: verification_mode="no_claims" → aggressive_rewrite."""

    def test_no_claims_aggressive_rewrite(self):
        state = _state(verification_mode="no_claims", is_hallucinated=True)
        assert should_heal(state) == "aggressive_rewrite"

    def test_no_claims_trumps_healing_target(self):
        """no_claims has higher priority than healing_target."""
        state = _state(
            verification_mode="no_claims",
            healing_target="targeted_healing",
            is_hallucinated=True,
        )
        # no_claims is checked before healing_target
        assert should_heal(state) == "aggressive_rewrite"


class TestHealingTargetRouting:
    """Rules 3-5: healing_target directs to specific healing strategies."""

    def test_targeted_healing(self):
        state = _state(
            healing_target="targeted_healing",
            is_hallucinated=True,
            grounding_score=0.5,
        )
        assert should_heal(state) == "targeted_healing"

    def test_retrieval_expansion(self):
        state = _state(
            healing_target="retrieval_expansion",
            is_hallucinated=True,
            grounding_score=0.3,
        )
        assert should_heal(state) == "retrieval_expansion"

    def test_aggressive_rewrite(self):
        state = _state(
            healing_target="aggressive_rewrite",
            is_hallucinated=True,
            grounding_score=0.1,
        )
        assert should_heal(state) == "aggressive_rewrite"

    def test_healing_target_none_is_noop(self):
        """healing_target="none" should not match any targeted route.
        Falls through to hallucination check."""
        state = _state(
            healing_target="none",
            is_hallucinated=False,
            grounding_score=0.9,
            verification_mode="claims_verified",
        )
        assert should_heal(state) == "output"


class TestFallbackHealing:
    """Rule 6: is_hallucinated or below threshold → targeted_healing (fallback)."""

    def test_hallucinated_true_fallback(self):
        """is_hallucinated=True with empty healing_target → fallback to targeted_healing."""
        state = _state(
            is_hallucinated=True,
            grounding_score=0.2,
            healing_target="",
        )
        assert should_heal(state) == "targeted_healing"

    def test_below_threshold_fallback(self):
        """grounding_score below threshold with no healing_target → fallback."""
        state = _state(
            is_hallucinated=False,
            grounding_score=0.1,
            healing_target="",
        )
        assert should_heal(state) == "targeted_healing"

    def test_exactly_at_threshold_output(self):
        """Exactly at threshold (0.5) with no hallucination → output."""
        state = _state(
            is_hallucinated=False,
            grounding_score=0.5,
            healing_target="",
        )
        assert should_heal(state) == "output"

    def test_above_threshold_output(self):
        """Above threshold with no hallucination → output."""
        state = _state(
            is_hallucinated=False,
            grounding_score=0.8,
            healing_target="",
        )
        assert should_heal(state) == "output"


class TestHappyPath:
    """Rule 7: all good → output."""

    def test_perfect_grounding_output(self):
        state = _state(
            is_hallucinated=False,
            grounding_score=1.0,
            healing_target="none",
        )
        assert should_heal(state) == "output"

    def test_hallucinated_but_healed_by_retry(self):
        """After healing, retry_count incremented, but if score still low,
        should continue healing."""
        state = _state(
            retry_count=0,
            max_retries=2,
            is_hallucinated=False,
            grounding_score=0.6,
            healing_target="",
        )
        assert should_heal(state) == "output"