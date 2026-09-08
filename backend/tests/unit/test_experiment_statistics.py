import numpy as np
from backend.experiments.statistics import (
    bootstrap_confidence_interval,
    compute_statistical_summary,
    paired_wilcoxon_test,
)


def test_bootstrap_confidence_interval():
    # Normal distribution with mean ~ 0.8
    rng = np.random.default_rng(42)
    data = list(rng.normal(0.8, 0.05, 50))

    ci_lower, ci_upper = bootstrap_confidence_interval(data, seed=42)
    assert ci_lower < 0.82
    assert ci_upper > 0.78
    assert ci_lower < ci_upper


def test_paired_wilcoxon_identical():
    data = [0.8, 0.85, 0.9, 0.75, 0.7]
    stat, pval = paired_wilcoxon_test(data, data)
    assert pval == 1.0


def test_paired_wilcoxon_significant_difference():
    baseline = [0.5, 0.52, 0.48, 0.51, 0.49, 0.50, 0.53, 0.47, 0.52, 0.51]
    candidate = [0.85, 0.88, 0.82, 0.86, 0.84, 0.87, 0.89, 0.83, 0.86, 0.85]

    summary = compute_statistical_summary(candidate, baseline)
    assert summary.is_statistically_significant is True
    assert summary.wilcoxon_p_value is not None
    assert summary.wilcoxon_p_value < 0.05
    assert summary.effect_size is not None
    assert summary.effect_size > 1.0
