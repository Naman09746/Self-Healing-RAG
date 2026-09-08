from backend.experiments.models import ObjectiveConfig
from backend.experiments.objective import calculate_objective_score


def test_objective_score_within_sla():
    config = ObjectiveConfig(max_p95_latency_ms=2000.0)

    score = calculate_objective_score(
        mean_quality=0.85,
        p95_latency_ms=1500.0,  # Below SLA threshold
        total_tokens=10000,
        mean_healing_count=0.0,
        config=config,
    )
    # Cost deduction: 10 * 0.002 = 0.02
    # Expected: 0.85 - 0.02 = 0.83
    assert abs(score - 0.83) < 0.01


def test_objective_score_exceeding_sla():
    config = ObjectiveConfig(max_p95_latency_ms=1000.0)

    score = calculate_objective_score(
        mean_quality=0.85,
        p95_latency_ms=2000.0,  # 1000ms over SLA!
        total_tokens=5000,
        mean_healing_count=2.0,  # 2 healing rewrites
        config=config,
    )
    # Excess latency penalty: 1000 * 0.0005 = 0.50
    # Healing penalty: 2 * 0.05 = 0.10
    # Cost deduction: 5 * 0.002 = 0.01
    # Expected: 0.85 - 0.50 - 0.10 - 0.01 = 0.24
    assert abs(score - 0.24) < 0.01
