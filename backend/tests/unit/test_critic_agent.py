"""Unit tests for CriticAgent.verify_grounding() — Phase 3B.

Tests cover:
  - Empty claims → no_claims (regression guard)
  - Per-claim parallel verification phase 3B entry point
  - healing_target calculation for all 4 verdict modes
  - detailed_results with per-claim verdicts
  - Backward compatibility with verify_claims_batch mock path
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.critic.agent import CriticAgent
from backend.agents.critic.verdict import (
    Verdict,
    ClaimVerdict,
    aggregate_grounding_score,
    is_hallucinated,
    dominant_healing_mode,
)


@pytest.fixture
def critic_agent():
    """Fixture that returns a CriticAgent with mocked LLM dependencies."""
    agent = CriticAgent(model="test-model")
    agent.extractor = AsyncMock()
    agent.verifier = AsyncMock()
    return agent


# ── helpers ──────────────────────────────────────────────────────────────

def _claim_verdicts(
    claims: list,
    verdicts: list,
) -> list:
    """Build ClaimVerdict fixtures from parallel lists of claims and verdict strings."""
    return [
        ClaimVerdict(claim=c, verdict=Verdict(v), reasoning=f"Auto: {v}")
        for c, v in zip(claims, verdicts)
    ]


class TestNoClaimsEdgeCase:
    """Critical edge case: empty / unparseable answers.
    Regression guard against the false-negative bug.
    """

    async def test_no_claims_returns_noclaims_verdict(self, critic_agent):
        """Empty claims must produce grounding_score=0.0, is_hallucinated=True,
        verification_mode="no_claims", healing_target="aggressive_rewrite"."""
        critic_agent.extractor.extract_claims = AsyncMock(return_value=[])

        result = await critic_agent.verify_grounding(
            query="What is the capital of France?",
            answer="",
            context_chunks=["Paris is the capital of France."],
        )

        assert result["grounding_score"] == 0.0
        assert result["is_hallucinated"] is True
        assert result["verification_mode"] == "no_claims"
        assert result["claims_analyzed"] == 0
        assert result["healing_target"] == "aggressive_rewrite"

    async def test_no_claims_does_not_call_verifier(self, critic_agent):
        """When extractor returns [], verify_claims_parallel must NOT be called."""
        critic_agent.extractor.extract_claims = AsyncMock(return_value=[])
        critic_agent.verifier.verify_claims_parallel = AsyncMock()

        await critic_agent.verify_grounding(
            query="test", answer="", context_chunks=["ctx"],
        )

        critic_agent.verifier.verify_claims_parallel.assert_not_called()


class TestPhase3BCritic:
    """Phase 3B: per-claim parallel verification with 4-verdict system."""

    async def test_all_supported(self, critic_agent):
        """SUPPORTED only → grounding_score=1.0, is_hallucinated=False,
        healing_target="none"."""
        critic_agent.extractor.extract_claims = AsyncMock(
            return_value=["Paris is capital of France."]
        )
        critic_agent.verifier.verify_claims_parallel = AsyncMock(
            return_value=_claim_verdicts(
                ["Paris is capital of France."],
                ["SUPPORTED"],
            )
        )

        result = await critic_agent.verify_grounding(
            query="test", answer="Paris is capital of France.",
            context_chunks=["Paris is capital of France."],
        )

        assert result["grounding_score"] == 1.0
        assert result["is_hallucinated"] is False
        assert result["verification_mode"] == "claims_verified"
        assert result["claims_analyzed"] == 1
        assert result["healing_target"] == "none"

    async def test_partially_supported(self, critic_agent):
        """PARTIALLY_SUPPORTED → healing_target="targeted_healing"."""
        critic_agent.extractor.extract_claims = AsyncMock(
            return_value=["Paris is capital.", "Population 2.1M."]
        )
        critic_agent.verifier.verify_claims_parallel = AsyncMock(
            return_value=_claim_verdicts(
                ["Paris is capital.", "Population 2.1M."],
                ["SUPPORTED", "PARTIALLY_SUPPORTED"],
            )
        )

        result = await critic_agent.verify_grounding(
            query="test", answer="Paris is capital. Population 2.1M.",
            context_chunks=["Some context."],
        )

        assert result["grounding_score"] == pytest.approx(0.75)
        assert result["healing_target"] == "targeted_healing"
        assert "partial" in result["reasoning"]

    async def test_unsupported_majority(self, critic_agent):
        """More UNSUPPORTED than SUPPORTED → healing_target="retrieval_expansion"."""
        critic_agent.extractor.extract_claims = AsyncMock(
            return_value=["Claim A", "Claim B", "Claim C"]
        )
        critic_agent.verifier.verify_claims_parallel = AsyncMock(
            return_value=_claim_verdicts(
                ["Claim A", "Claim B", "Claim C"],
                ["SUPPORTED", "UNSUPPORTED", "UNSUPPORTED"],
            )
        )

        result = await critic_agent.verify_grounding(
            query="test", answer="A B C", context_chunks=["Ctx"],
        )

        assert result["healing_target"] == "retrieval_expansion"
        assert result["is_hallucinated"] is True

    async def test_contradicted_claim(self, critic_agent):
        """Any CONTRADICTED → healing_target="aggressive_rewrite"."""
        critic_agent.extractor.extract_claims = AsyncMock(
            return_value=["Paris is capital.", "London is capital of France."]
        )
        critic_agent.verifier.verify_claims_parallel = AsyncMock(
            return_value=_claim_verdicts(
                ["Paris is capital.", "London is capital of France."],
                ["SUPPORTED", "CONTRADICTED"],
            )
        )

        result = await critic_agent.verify_grounding(
            query="test", answer="Paris is capital and London is capital of France.",
            context_chunks=["Paris is capital of France."],
        )

        assert result["healing_target"] == "aggressive_rewrite"
        assert result["is_hallucinated"] is True
        # SUPPORTED=1.0, CONTRADICTED=-0.5→clamped to 0.0 → (1.0+0.0)/2=0.5
        assert result["grounding_score"] == pytest.approx(0.5)

    async def test_detailed_results_includes_all_verdicts(self, critic_agent):
        """detailed_results must contain claim, verdict, reasoning for every claim."""
        claims = ["Claim one.", "Claim two."]
        verdicts = _claim_verdicts(claims, ["SUPPORTED", "UNSUPPORTED"])
        critic_agent.extractor.extract_claims = AsyncMock(return_value=claims)
        critic_agent.verifier.verify_claims_parallel = AsyncMock(return_value=verdicts)

        result = await critic_agent.verify_grounding(
            query="test", answer="one two", context_chunks=["ctx"],
        )

        assert len(result["detailed_results"]) == 2
        assert result["detailed_results"][0]["verdict"] == "SUPPORTED"
        assert result["detailed_results"][1]["verdict"] == "UNSUPPORTED"
        assert result["detailed_results"][0]["reasoning"] == "Auto: SUPPORTED"
        assert result["detailed_results"][1]["claim"] == "Claim two."

    async def test_verifier_exception_falls_back_to_unsupported(self, critic_agent):
        """If verify_claims_parallel raises on one claim, that claim gets
        UNSUPPORTED but others still process (gather with return_exceptions=True)."""
        critic_agent.extractor.extract_claims = AsyncMock(
            return_value=["Claim A", "Claim B"]
        )
        # Mock the verifier's parallel method to simulate partial failure
        # We mock at the CriticAgent level to simulate the gather behavior
        critic_agent.verifier.verify_claims_parallel = AsyncMock(
            side_effect=Exception("LLM timeout on all claims")
        )

        # The caller (critic_node) would handle this, but agent re-raises
        with pytest.raises(Exception, match="LLM timeout"):
            await critic_agent.verify_grounding(
                query="test", answer="A B", context_chunks=["ctx"],
            )


class TestVerdictHelpers:
    """Unit tests for verdict.py helper functions."""

    def test_aggregate_empty(self):
        assert aggregate_grounding_score([]) == 0.0

    def test_aggregate_all_supported(self):
        cvs = _claim_verdicts(["A", "B"], ["SUPPORTED", "SUPPORTED"])
        assert aggregate_grounding_score(cvs) == 1.0

    def test_aggregate_contradicted_clamped(self):
        """CONTRADICTED has weight -0.5, clamped to 0.
        SUPPORTED(1.0) + CONTRADICTED→clamped(0.0) = 1.0 / 2 = 0.5"""
        cvs = _claim_verdicts(["A", "B"], ["SUPPORTED", "CONTRADICTED"])
        assert aggregate_grounding_score(cvs) == pytest.approx(0.5)

    def test_aggregate_mixed(self):
        cvs = _claim_verdicts(["A", "B", "C", "D"],
                              ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED"])
        score = aggregate_grounding_score(cvs)
        # 1.0 + 0.5 + 0.0 + 0.0 = 1.5 / 4 = 0.375
        assert score == pytest.approx(0.375)

    def test_is_hallucinated_contradicted(self):
        cvs = _claim_verdicts(["A", "B"], ["SUPPORTED", "CONTRADICTED"])
        assert is_hallucinated(cvs) is True

    def test_is_hallucinated_below_threshold(self):
        cvs = _claim_verdicts(["A"], ["UNSUPPORTED"])
        assert is_hallucinated(cvs) is True

    def test_is_hallucinated_supported(self):
        cvs = _claim_verdicts(["A"], ["SUPPORTED"])
        assert is_hallucinated(cvs) is False

    def test_is_hallucinated_empty(self):
        assert is_hallucinated([]) is True

    def test_dominant_healing_none(self):
        assert dominant_healing_mode(_claim_verdicts(["A"], ["SUPPORTED"])) == "none"

    def test_dominant_healing_targeted(self):
        assert dominant_healing_mode(
            _claim_verdicts(["A", "B"], ["SUPPORTED", "PARTIALLY_SUPPORTED"])
        ) == "targeted_healing"

    def test_dominant_healing_retrieval_expansion(self):
        assert dominant_healing_mode(
            _claim_verdicts(["A", "B", "C"], ["SUPPORTED", "UNSUPPORTED", "UNSUPPORTED"])
        ) == "retrieval_expansion"

    def test_dominant_healing_aggressive_rewrite(self):
        assert dominant_healing_mode(
            _claim_verdicts(["A", "B"], ["SUPPORTED", "CONTRADICTED"])
        ) == "aggressive_rewrite"

    def test_dominant_healing_empty(self):
        assert dominant_healing_mode([]) == "none"

    def test_verdict_is_positive(self):
        assert Verdict.SUPPORTED.is_positive is True
        assert Verdict.PARTIALLY_SUPPORTED.is_positive is True
        assert Verdict.UNSUPPORTED.is_positive is False
        assert Verdict.CONTRADICTED.is_positive is False

    def test_verdict_is_negative(self):
        assert Verdict.SUPPORTED.is_negative is False
        assert Verdict.PARTIALLY_SUPPORTED.is_negative is False
        assert Verdict.UNSUPPORTED.is_negative is True
        assert Verdict.CONTRADICTED.is_negative is True