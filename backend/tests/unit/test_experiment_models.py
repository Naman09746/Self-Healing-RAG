import pytest
from backend.experiments.models import (
    BudgetConfig,
    CandidateProposal,
    ObjectiveConfig,
    ObjectivePenalties,
    ObjectiveWeights,
    StatisticalSummary,
    StrategyType,
    TrialQueryResult,
    TrialResult,
    TrialStatus,
)


def test_objective_config_defaults():
    config = ObjectiveConfig()
    assert config.name == "balanced_optimization"
    assert config.max_p95_latency_ms == 2000.0
    assert config.weights.faithfulness == 0.35
    assert config.penalties.latency == 0.0005


def test_budget_config_validation():
    budget = BudgetConfig(max_experiments=15, max_total_seconds=1800)
    assert budget.max_experiments == 15
    assert budget.query_timeout_seconds == 30
    assert budget.max_consecutive_failures == 3

    with pytest.raises(ValueError):
        BudgetConfig(max_experiments=0)


def test_candidate_proposal_serialization():
    proposal = CandidateProposal(
        hypothesis="Increasing hybrid alpha will improve context precision",
        expected_outcome="Precision +0.05, Latency +50ms",
        parameters={"hybrid_search_alpha": 0.7, "top_k": 7},
        justification="BM25 matches keyword exactness for technical entities.",
    )
    dumped = proposal.model_dump()
    assert dumped["parameters"]["top_k"] == 7
    assert "precision" in dumped["hypothesis"].lower()


def test_trial_query_result_fields():
    result = TrialQueryResult(
        query_id="q1",
        query_text="What is RAG?",
        generated_answer="RAG stands for Retrieval-Augmented Generation.",
        faithfulness=0.9,
        answer_relevance=0.85,
        context_precision=0.8,
        context_recall=0.75,
        composite_quality=0.83,
        latency_ms=450.0,
        healing_count=1,
    )
    assert result.query_id == "q1"
    assert result.composite_quality == 0.83
    assert result.latency_ms == 450.0
