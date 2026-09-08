from typing import Optional
from backend.experiments.models import ObjectiveConfig


def calculate_objective_score(
    mean_quality: float,
    p95_latency_ms: float,
    total_tokens: int,
    mean_healing_count: float,
    config: ObjectiveConfig,
) -> float:
    """Calculate the scalar objective score incorporating SLA penalties.

    Score = mean_quality
            - latency_penalty * max(0, p95_latency_ms - max_p95_latency_ms)
            - cost_penalty * (total_tokens / 1000 * cost_per_1k)
            - healing_penalty * mean_healing_count
    """
    # 1. Base Quality
    score = mean_quality

    # 2. Latency Penalty (only applies if p95 exceeds SLA threshold)
    if p95_latency_ms > config.max_p95_latency_ms:
        excess_ms = p95_latency_ms - config.max_p95_latency_ms
        latency_deduction = config.penalties.latency * excess_ms
        score -= latency_deduction

    # 3. Simulated Token Cost Penalty ($0.002 per 1k tokens standard)
    simulated_cost = (total_tokens / 1000.0) * 0.002
    cost_deduction = config.penalties.cost * simulated_cost
    score -= cost_deduction

    # 4. Self-Healing Penalty (discourages configurations that trigger constant query rewrites)
    healing_deduction = config.penalties.healing * mean_healing_count
    score -= healing_deduction

    return round(float(score), 4)
