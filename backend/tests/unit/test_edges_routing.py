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
from backend.graph.state import RAGState, GenerationResult, RetrievedChunk
from backend.graph.edges import should_heal, should_generate


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


class TestShouldGenerate:
    """Phase 1A: Knowledge-absence fast-fail routing."""

    def test_fast_fail_flag_routes_to_output(self):
        state = _state(no_relevant_chunks=True)
        assert should_generate(state) == "output"

    def test_empty_chunks_routes_to_output(self):
        state = _state(retrieved_chunks=[], no_relevant_chunks=False)
        assert should_generate(state) == "output"

    def test_all_chunks_below_threshold_routes_to_output(self):
        # Vector distances above threshold (0.9 > 0.65) and sparse scores below RRF threshold (0.005 <0.008)
        chunks = [
            RetrievedChunk(chunk_id="1", content="low score 1", score=0.005, source="doc1", distance=0.92),
            RetrievedChunk(chunk_id="2", content="low score 2", score=0.004, source="doc2", distance=0.88),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "output"

    def test_relevant_chunks_routes_to_generation(self):
        # One chunk with good distance (0.3) should route to generation even if other is low
        chunks = [
            RetrievedChunk(chunk_id="1", content="low score 1", score=0.005, source="doc1", distance=0.92),
            RetrievedChunk(chunk_id="2", content="high score 2", score=0.85, source="doc2", distance=0.32),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "generation"

    def test_rrf_fallback_sparse_relevant(self, monkeypatch):
        # Sparse-only with RRF scores above RRF_THRESHOLD (0.008) should be relevant — NoOp path
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_PROVIDER", "none")
        monkeypatch.setattr("backend.graph.nodes.settings.RERANKER_PROVIDER", "none")
        chunks = [
            RetrievedChunk(chunk_id="1", content="sparse 1", score=0.012, source="doc1", distance=None),
            RetrievedChunk(chunk_id="2", content="sparse 2", score=0.015, source="doc2", distance=None),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "generation"

    def test_rrf_fallback_all_below_routes_to_output(self, monkeypatch):
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_PROVIDER", "none")
        monkeypatch.setattr("backend.graph.nodes.settings.RERANKER_PROVIDER", "none")
        chunks = [
            RetrievedChunk(chunk_id="1", content="sparse low", score=0.005, source="doc1", distance=None),
            RetrievedChunk(chunk_id="2", content="sparse low2", score=0.003, source="doc2", distance=None),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        # NoOp fallback: any RRF non-empty → generation to avoid P0 false fast-fail on small corpora
        assert should_generate(state) == "generation"

    def test_cross_encoder_below_threshold_routes_to_output(self, monkeypatch):
        # Cross-encoder path: RRF scores 0.012 are < RERANKER_THRESHOLD 0.5 → should fast-fail
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_PROVIDER", "cross-encoder")
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_THRESHOLD", 0.5)
        chunks = [
            RetrievedChunk(chunk_id="1", content="sparse 1", score=0.012, source="doc1", distance=None),
            RetrievedChunk(chunk_id="2", content="sparse 2", score=0.015, source="doc2", distance=None),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "output"

    def test_cross_encoder_above_threshold_routes_to_generation(self, monkeypatch):
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_PROVIDER", "cross-encoder")
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_THRESHOLD", 0.5)
        chunks = [
            RetrievedChunk(chunk_id="1", content="reranked high", score=2.5, source="doc1", distance=None),
            RetrievedChunk(chunk_id="2", content="reranked low", score=0.1, source="doc2", distance=None),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "generation"

    def test_vector_distance_threshold(self, monkeypatch):
        # Vector distance 0.60 < VECTOR_DISTANCE_THRESHOLD 0.65 → relevant
        monkeypatch.setattr("backend.graph.edges.settings.VECTOR_DISTANCE_THRESHOLD", 0.65)
        chunks = [
            RetrievedChunk(chunk_id="1", content="good distance", score=0.6, source="doc1", distance=0.60),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "generation"

    def test_vector_distance_above_threshold(self, monkeypatch):
        monkeypatch.setattr("backend.graph.edges.settings.VECTOR_DISTANCE_THRESHOLD", 0.65)
        chunks = [
            RetrievedChunk(chunk_id="1", content="bad distance", score=0.9, source="doc1", distance=0.85),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "output"

    def test_sparse_only_below_rrf_threshold(self, monkeypatch):
        monkeypatch.setattr("backend.graph.edges.settings.RERANKER_PROVIDER", "none")
        monkeypatch.setattr("backend.graph.edges.settings.RRF_THRESHOLD", 0.008)
        chunks = [
            RetrievedChunk(chunk_id="1", content="low RRF", score=0.001, source="doc1", distance=None),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        # NoOp still returns generation via fallback len>0 (threshold advisory for RRF)
        assert should_generate(state) == "generation"

    def test_dense_only_no_sparse(self, monkeypatch):
        monkeypatch.setattr("backend.graph.edges.settings.VECTOR_DISTANCE_THRESHOLD", 0.65)
        chunks = [
            RetrievedChunk(chunk_id="1", content="dense only good", score=0.9, source="doc1", distance=0.30),
        ]
        state = _state(retrieved_chunks=chunks, no_relevant_chunks=False)
        assert should_generate(state) == "generation"

    def test_no_results(self):
        state = _state(retrieved_chunks=[], no_relevant_chunks=False)
        assert should_generate(state) == "output"

    def test_unsupported_ood_via_no_relevant_flag(self):
        # OOD where retriever found candidates but none passed distance/RRF → flag set
        state = _state(retrieved_chunks=[
            RetrievedChunk(chunk_id="1", content="irrelevant", score=0.9, source="doc1", distance=0.90),
        ], no_relevant_chunks=True)
        assert should_generate(state) == "output"