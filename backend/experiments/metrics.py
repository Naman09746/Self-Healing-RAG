from typing import List
import numpy as np
from backend.experiments.models import ObjectiveWeights, TrialQueryResult


def compute_composite_quality(
    faithfulness: float,
    answer_relevance: float,
    context_precision: float,
    context_recall: float,
    weights: ObjectiveWeights,
) -> float:
    """Calculate weighted composite quality score bounded in [0.0, 1.0]."""
    total_w = (
        weights.faithfulness
        + weights.answer_relevance
        + weights.context_precision
        + weights.context_recall
    )
    if total_w <= 0.0:
        total_w = 1.0

    raw = (
        weights.faithfulness * faithfulness
        + weights.answer_relevance * answer_relevance
        + weights.context_precision * context_precision
        + weights.context_recall * context_recall
    ) / total_w

    return round(max(0.0, min(1.0, float(raw))), 4)


def compute_latency_percentiles(latencies_ms: List[float]) -> dict:
    """Calculate latency distribution metrics (mean, p50, p90, p95, p99)."""
    if not latencies_ms:
        return {"mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

    arr = np.array(latencies_ms, dtype=float)
    return {
        "mean": round(float(np.mean(arr)), 2),
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p90": round(float(np.percentile(arr, 90)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "p99": round(float(np.percentile(arr, 99)), 2),
    }


def compute_trial_aggregates(query_results: List[TrialQueryResult], weights: ObjectiveWeights) -> dict:
    """Aggregate per-query evaluation telemetry into trial-level metrics."""
    if not query_results:
        return {
            "mean_quality": 0.0,
            "mean_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "total_tokens": 0,
            "mean_healing_count": 0.0,
            "quality_scores": [],
        }

    quality_scores = [q.composite_quality for q in query_results]
    latencies = [q.latency_ms for q in query_results]
    tokens = sum(q.token_count for q in query_results)
    healings = sum(q.healing_count for q in query_results)

    percentiles = compute_latency_percentiles(latencies)

    return {
        "mean_quality": round(float(np.mean(quality_scores)), 4),
        "mean_latency_ms": percentiles["mean"],
        "p95_latency_ms": percentiles["p95"],
        "total_tokens": tokens,
        "mean_healing_count": round(healings / len(query_results), 2),
        "quality_scores": quality_scores,
    }
