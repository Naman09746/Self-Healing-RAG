from backend.experiments.baselines.bayesian import BayesianAdaptiveBaseline
from backend.experiments.baselines.default import DefaultBaseline
from backend.experiments.baselines.grid import GridSearchBaseline
from backend.experiments.baselines.random import RandomSearchBaseline
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.models import StrategyType, TrialResult


def test_default_baseline():
    registry = ConfigRegistry()
    baseline = DefaultBaseline(registry)
    params = baseline.select_next()
    assert params["top_k"] == 5
    assert params["chunk_variant"] == "c700_o100"


def test_random_search_baseline():
    registry = ConfigRegistry()
    baseline = RandomSearchBaseline(registry, seed=123)
    params = baseline.select_next()
    assert 1 <= params["top_k"] <= 20
    assert 0.0 <= params["hybrid_search_alpha"] <= 1.0
    assert params["chunk_variant"] in ["c500_o50", "c700_o100", "c1500_o300"]


def test_grid_search_baseline():
    registry = ConfigRegistry()
    grid = GridSearchBaseline(registry)
    p1 = grid.select_next()
    p2 = grid.select_next()
    assert p1 is not None
    assert p2 is not None


def test_bayesian_baseline_with_history():
    registry = ConfigRegistry()
    bayesian = BayesianAdaptiveBaseline(registry, seed=42)

    # Empty history falls back to random
    p_initial = bayesian.select_next([])
    assert p_initial is not None

    # Synthetic trial history with 3 trials
    trials = [
        TrialResult(
            trial_id="t1",
            campaign_id="c1",
            trial_number=1,
            strategy=StrategyType.RANDOM,
            parameters={"top_k": 3, "hybrid_search_alpha": 0.3},
            objective_score=0.65,
        ),
        TrialResult(
            trial_id="t2",
            campaign_id="c1",
            trial_number=2,
            strategy=StrategyType.RANDOM,
            parameters={"top_k": 5, "hybrid_search_alpha": 0.5},
            objective_score=0.75,
        ),
        TrialResult(
            trial_id="t3",
            campaign_id="c1",
            trial_number=3,
            strategy=StrategyType.RANDOM,
            parameters={"top_k": 8, "hybrid_search_alpha": 0.7},
            objective_score=0.82,
        ),
    ]

    p_gp = bayesian.select_next(trials)
    assert 1 <= p_gp["top_k"] <= 20
    assert 0.0 <= p_gp["hybrid_search_alpha"] <= 1.0
