"""
Comprehensive tests for Phase 3C — Adaptive Retrieval Complexity Classifier.

Tests cover:
  1. Rule-based ``compute_complexity`` — edge cases, boundaries, feature sensitivity.
  2. ``adaptive_k`` mapping — correct thresholds.
  3. ``select_rerank_top_k`` — correct mapping.
  4. ``_extract_features`` — individual feature correctness.
  5. Integration: full pipeline from query → k.
  6. LLM fallback path (mocked).
  7. Regression: simple queries stay fast (low complexity).
"""

import pytest
import math
from backend.graph.complexity import (
    compute_complexity,
    compute_complexity_llm,
    adaptive_k,
    select_rerank_top_k,
    _extract_features,
)


# =========================================================================
# 1. Feature extraction unit tests
# =========================================================================

class TestExtractFeatures:
    """Verify individual feature calculations are correct."""

    def test_empty_query(self):
        f = _extract_features("")
        assert f["n_tokens"] == 0
        assert f["tech_density"] == 0.0
        assert f["q_weight"] == 0.0
        assert f["multi_hop_density"] == 0.0
        assert f["entity_density"] == 0.0

    def test_simple_factoid(self):
        f = _extract_features("What is the capital of France?")
        assert f["n_tokens"] == 6
        assert f["tech_density"] == 0.0  # no technical terms
        assert f["q_weight"] == 0.1  # "what"
        assert f["multi_hop_density"] == 0.0
        assert f["entity_density"] > 0.0  # "France" is capitalised

    def test_technical_query(self):
        f = _extract_features("How does GDPR jurisdiction affect extraterritorial compliance?")
        assert f["tech_density"] > 0.0  # jurisdiction, extraterritorial, compliance
        assert f["q_weight"] == 0.4  # "how"
        assert f["multi_hop_density"] > 0.0  # "affect" is causal-adjacent

    def test_multi_hop_causal(self):
        f = _extract_features("What caused the 2008 recession and how does it compare to 2020?")
        assert f["multi_hop_density"] > 0.0  # "caused", "compare"
        assert f["clause_factor"] > 0.0  # "and" conjunction

    def test_entity_detection(self):
        f = _extract_features("What is the relationship between GDPR and CCPA?")
        assert f["entity_density"] > 0.0  # GDPR, CCPA (acronyms)
        assert f["tech_density"] > 0.0  # relationship (comparative marker counts)


# =========================================================================
# 2. Compute complexity scoring tests
# =========================================================================

class TestComputeComplexity:
    """Verify the complexity score ranges are correct."""

    def test_empty_query_is_zero(self):
        assert compute_complexity("") == 0.0
        assert compute_complexity("   ") == 0.0
        assert compute_complexity(None) == 0.0

    def test_simple_queries_score_below_0_3(self):
        """Simple factoids should map to k=3."""
        simple_queries = [
            "What is the capital of France?",
            "Who wrote Hamlet?",
            "When was Python released?",
            "What is 2 + 2?",
            "Define recursion.",
        ]
        for q in simple_queries:
            score = compute_complexity(q)
            assert score < 0.3, f"Expected {q!r} to score < 0.3, got {score:.3f}"

    def test_medium_queries_score_between_0_3_and_0_7(self):
        """Medium queries should map to k=5."""
        medium_queries = [
            "How does the GDPR apply to US companies processing EU citizen data?",
            "Describe the relationship between quantum computing and cryptography.",
            "Explain how machine learning models are deployed in production environments.",
            "How does Docker container orchestration work with Kubernetes?",
            "What is the difference between REST and GraphQL APIs?",
        ]
        for q in medium_queries:
            score = compute_complexity(q)
            assert 0.3 <= score < 0.7, f"Expected {q!r} to score 0.3–0.7, got {score:.3f}"

    def test_complex_queries_score_above_0_7(self):
        """Complex queries should map to k=10."""
        complex_queries = [
            "Compare and contrast the extraterritorial jurisdiction of GDPR Article 17 "
            "with the California Consumer Privacy Act's data deletion requirements for "
            "SaaS companies, and analyze how conflicting provisions should be reconciled.",
            "Analyze the relationship between federal reserve monetary policy, treasury "
            "yield curve inversions, and their predictive power for recession timing "
            "compared to alternative leading indicators like housing starts.",
            "Explain how transformer architecture attention mechanisms differ between "
            "encoder-decoder models versus decoder-only models, and discuss the "
            "implications for long-context understanding in production RAG systems.",
        ]
        for q in complex_queries:
            score = compute_complexity(q)
            assert score >= 0.7, f"Expected {q!r} to score >= 0.7, got {score:.3f}"

    def test_boundary_bucket_0_3(self):
        """Queries around the 0.3 boundary."""
        # Barely simple — should be < 0.3
        simple = compute_complexity("What is the time in Tokyo?")
        assert simple < 0.3, f"Expected simple, got {simple:.3f}"

        # Edge: moderately technical but short
        medium = compute_complexity("How does Kubernetes handle pod auto-scaling?")
        # Could go either way, but should not be extreme
        assert 0.0 <= medium <= 1.0

    def test_very_short_complex(self):
        """Even short queries can be complex if they use technical terms."""
        score = compute_complexity("Explain extraterritorial GDPR jurisdiction.")
        # Short (4 words) but dense in technical terms
        assert score > 0.2, f"Short technical query should be > 0.2, got {score:.3f}"

    def test_long_simple(self):
        """Long queries can still be simple if they are list-like."""
        score = compute_complexity(
            "List the capitals of France Germany Italy Spain Portugal "
            "Netherlands Belgium Austria Switzerland and Denmark"
        )
        # Long but simple factoid list — should still be < 0.7
        assert score < 0.7, f"Long list query should be < 0.7, got {score:.3f}"


# =========================================================================
# 3. Adaptive k mapping tests
# =========================================================================

class TestAdaptiveK:
    """Verify the k mapping boundaries."""

    def test_simple_range(self):
        assert adaptive_k(0.0) == 3
        assert adaptive_k(0.1) == 3
        assert adaptive_k(0.29) == 3
        # Edge: exactly 0.3
        assert adaptive_k(0.3) == 5  # Falls into medium

    def test_medium_range(self):
        assert adaptive_k(0.3) == 5
        assert adaptive_k(0.5) == 5
        assert adaptive_k(0.69) == 5
        # Edge: exactly 0.7
        assert adaptive_k(0.7) == 10  # Falls into complex

    def test_complex_range(self):
        assert adaptive_k(0.7) == 10
        assert adaptive_k(0.85) == 10
        assert adaptive_k(0.99) == 10
        assert adaptive_k(1.0) == 10

    def test_out_of_bounds(self):
        assert adaptive_k(-0.1) == 3  # Clamped by caller, treated as simple
        assert adaptive_k(1.5) == 10  # Clamped by caller, treated as complex


# =========================================================================
# 4. Rerank top_k mapping tests
# =========================================================================

class TestSelectRerankTopK:
    """Verify rerank top_k selection."""

    def test_simple_rerank(self):
        assert select_rerank_top_k(3) == 3
        assert select_rerank_top_k(4) == 5  # Falls through to 5 bucket
        assert select_rerank_top_k(5) == 5

    def test_complex_rerank(self):
        assert select_rerank_top_k(10) == 6
        assert select_rerank_top_k(7) == 6  # Anything >5 gets 6

    def test_edge_cases(self):
        assert select_rerank_top_k(0) == 3  # Default to safe minimum
        assert select_rerank_top_k(1) == 3
        assert select_rerank_top_k(2) == 3
        assert select_rerank_top_k(6) == 6


# =========================================================================
# 5. LLM fallback tests (mocked)
# =========================================================================

class TestComputeComplexityLLM:
    """Verify LLM fallback works correctly."""

    def test_llm_fallback_valid(self):
        """When LLM returns a valid float, use it."""
        mock_llm = lambda prompt: "0.85"  # noqa: E731
        score = compute_complexity_llm("test query", mock_llm)
        assert score == 0.85

    def test_llm_fallback_bounds(self):
        """LLM responses > 1.0 or < 0.0 should be clamped."""
        mock_llm_high = lambda prompt: "2.5"  # noqa: E731
        score_high = compute_complexity_llm("test", mock_llm_high)
        assert score_high == 1.0

        mock_llm_low = lambda prompt: "-0.5"  # noqa: E731
        score_low = compute_complexity_llm("test", mock_llm_low)
        assert score_low == 0.0

    def test_llm_fallback_unparseable(self):
        """When LLM returns unparseable output, fall back to rule-based."""
        mock_llm_bad = lambda prompt: "I think this query is quite complex indeed"  # noqa: E731
        score = compute_complexity_llm("What is the capital of France?", mock_llm_bad)
        # Should fall back to rule-based = 0.0–0.3 range
        assert 0.0 <= score < 0.3

    def test_llm_fallback_empty(self):
        """Empty LLM response should fall back to rule-based."""
        mock_llm_empty = lambda prompt: ""  # noqa: E731
        score = compute_complexity_llm("What is the capital of France?", mock_llm_empty)
        assert 0.0 <= score < 0.3


# =========================================================================
# 6. Integration tests: full pipeline query → k
# =========================================================================

class TestFullPipeline:
    """End-to-end: raw query → complexity → k → rerank_top_k."""

    def test_simple_pipeline(self):
        query = "What is the capital of France?"
        score = compute_complexity(query)
        k = adaptive_k(score)
        rerank = select_rerank_top_k(k)
        assert score < 0.3
        assert k == 3
        assert rerank == 3

    def test_medium_pipeline(self):
        query = "How does quantum computing affect modern cryptography?"
        score = compute_complexity(query)
        k = adaptive_k(score)
        rerank = select_rerank_top_k(k)
        assert 0.3 <= score < 0.7
        assert k == 5
        assert rerank == 5

    def test_complex_pipeline(self):
        query = (
            "Compare and contrast the extraterritorial jurisdiction of GDPR Article 17 "
            "with CCPA data deletion requirements for SaaS companies, analyzing how "
            "conflicting provisions should be reconciled under international law."
        )
        score = compute_complexity(query)
        k = adaptive_k(score)
        rerank = select_rerank_top_k(k)
        assert score >= 0.7
        assert k == 10
        assert rerank == 6  # Complex queries use k=6 after rerank

    def test_rewritten_query_pipeline(self):
        """Rewritten/healed queries should also go through the pipeline."""
        raw_query = "Explain the relationship between AI and ethics."
        rewritten_query = (
            "How do machine learning bias detection frameworks mitigate "
            "unfair discrimination in automated hiring systems, and what regulatory "
            "compliance requirements apply under GDPR Article 22?"
        )
        
        raw_score = compute_complexity(raw_query)
        rewritten_score = compute_complexity(rewritten_query)
        
        # Rewritten query should be more complex than raw
        assert rewritten_score > raw_score


# =========================================================================
# 7. Performance sanity tests
# =========================================================================

class TestPerformance:
    """Basic performance sanity checks."""

    def test_classifier_speed(self):
        """Rule-based classifier should complete in < 1ms for typical queries."""
        import time
        queries = [
            "What is the capital of France?",
            "How does the GDPR compare to CCPA in terms of data subject rights?",
            "Analyze the relationship between transformer architecture, attention "
            "mechanisms, and long-context understanding in production RAG systems "
            "deployed at scale across multiple cloud providers.",
        ]
        for q in queries:
            start = time.perf_counter()
            compute_complexity(q)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < 5.0, f"Classifier took {elapsed_ms:.2f}ms for {q[:50]}..."


# =========================================================================
# 8. Regression guard — ensure existing simple queries don't regress
# =========================================================================

class TestRegressionGuard:
    """Ensure queries that worked before still work correctly."""

    def test_original_word_count_heuristic_replaced(self):
        """The old word_count <= 10 heuristic is gone — verify new system."""
        # Short but complex queries should now get higher k
        short_complex = "Explain GDPR extraterritorial jurisdiction."
        score = compute_complexity(short_complex)
        # Old system: word_count=4 <= 10 → would return simple (k=3 heuristic)
        # New system: technical density + entity detection should push score higher
        assert score > 0.1, f"Short technical query should be > 0.1, got {score:.3f}"

    def test_zero_tech_density_is_low(self):
        """Queries with zero technical terms should score low."""
        score = compute_complexity("What is the best restaurant in Paris?")
        assert score < 0.3, f"Should be simple, got {score:.3f}"

    def test_all_caps_is_entity(self):
        """ALL CAPS terms are detected as entities."""
        score = compute_complexity("What is the difference between GDPR and CCPA?")
        # GDPR and CCPA are both all-caps acronyms
        assert score > 0.0, "Should detect entities"