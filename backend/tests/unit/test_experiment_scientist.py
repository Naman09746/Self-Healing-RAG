import pytest
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.models import ObjectiveConfig, StrategyType, TrialResult
from backend.experiments.scientist.agent import AutonomousScientist


@pytest.mark.asyncio
async def test_scientist_offline_fallback():
    registry = ConfigRegistry()
    scientist = AutonomousScientist(registry=registry, ollama_host="http://localhost:99999")  # Non-existent host

    trial_history = [
        TrialResult(
            trial_id="t0",
            campaign_id="c0",
            trial_number=0,
            strategy=StrategyType.DEFAULT,
            parameters={"top_k": 5, "hybrid_search_alpha": 0.5},
            objective_score=0.72,
        ),
        TrialResult(
            trial_id="t1",
            campaign_id="c0",
            trial_number=1,
            strategy=StrategyType.BAYESIAN,
            parameters={"top_k": 7, "hybrid_search_alpha": 0.6},
            objective_score=0.79,
        ),
        TrialResult(
            trial_id="t2",
            campaign_id="c0",
            trial_number=2,
            strategy=StrategyType.BAYESIAN,
            parameters={"top_k": 8, "hybrid_search_alpha": 0.65},
            objective_score=0.84,
        ),
    ]

    proposal = await scientist.propose_candidate(
        objective=ObjectiveConfig(),
        trial_history=trial_history,
    )

    assert proposal is not None
    assert "parameters" in proposal.model_dump()
    assert 1 <= proposal.parameters["top_k"] <= 20
    assert 0.0 <= proposal.parameters["hybrid_search_alpha"] <= 1.0
    assert "Fallback" in proposal.hypothesis or "Surrogate" in proposal.hypothesis
