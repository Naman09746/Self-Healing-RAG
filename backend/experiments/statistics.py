import math
from typing import List, Optional, Tuple
import numpy as np
from scipy import stats
from backend.experiments.models import StatisticalSummary


def bootstrap_confidence_interval(
    data: List[float],
    n_resamples: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """Compute non-parametric bootstrap confidence interval for the sample mean."""
    if not data:
        return (0.0, 0.0)
    if len(data) == 1:
        return (data[0], data[0])

    rng = np.random.default_rng(seed)
    arr = np.array(data, dtype=float)
    n = len(arr)

    # Resample with replacement
    boot_samples = rng.choice(arr, size=(n_resamples, n), replace=True)
    boot_means = np.mean(boot_samples, axis=1)

    alpha = 1.0 - confidence_level
    lower_pct = (alpha / 2.0) * 100.0
    upper_pct = (1.0 - alpha / 2.0) * 100.0

    lower = float(np.percentile(boot_means, lower_pct))
    upper = float(np.percentile(boot_means, upper_pct))

    return (round(lower, 4), round(upper, 4))


def paired_wilcoxon_test(
    candidate: List[float],
    baseline: List[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Perform a two-sided paired Wilcoxon signed-rank test.

    Returns:
        (statistic, p_value), or (None, None) if samples are identical or invalid.
    """
    if len(candidate) != len(baseline) or len(candidate) < 5:
        return (None, None)

    diffs = np.array(candidate, dtype=float) - np.array(baseline, dtype=float)

    # If all differences are exactly 0, p-value is 1.0
    if np.all(diffs == 0.0):
        return (0.0, 1.0)

    try:
        res = stats.wilcoxon(candidate, baseline, zero_method="wilcox", alternative="two-sided")
        stat = float(res.statistic)
        pval = float(res.pvalue)
        return (stat, pval)
    except Exception:
        return (None, None)


def compute_statistical_summary(
    candidate_scores: List[float],
    baseline_scores: Optional[List[float]] = None,
    alpha_threshold: float = 0.05,
) -> StatisticalSummary:
    """Generate a complete StatisticalSummary given candidate and optional baseline scores."""
    if not candidate_scores:
        return StatisticalSummary()

    arr = np.array(candidate_scores, dtype=float)
    n = len(arr)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    median_val = float(np.median(arr))

    ci_lower, ci_upper = bootstrap_confidence_interval(candidate_scores)

    summary = StatisticalSummary(
        sample_size=n,
        mean=round(mean_val, 4),
        std_dev=round(std_val, 4),
        median=round(median_val, 4),
        ci_lower_95=ci_lower,
        ci_upper_95=ci_upper,
    )

    if baseline_scores and len(baseline_scores) == n:
        stat, pval = paired_wilcoxon_test(candidate_scores, baseline_scores)
        summary.wilcoxon_p_value = round(pval, 5) if pval is not None else None

        # Calculate Cohen's d or paired mean difference
        base_arr = np.array(baseline_scores, dtype=float)
        diff_mean = float(np.mean(arr - base_arr))
        pooled_std = math.sqrt((np.var(arr, ddof=1) + np.var(base_arr, ddof=1)) / 2.0) if n > 1 else 1.0
        effect_size = (diff_mean / pooled_std) if pooled_std > 0 else 0.0
        summary.effect_size = round(effect_size, 4)

        # Significant if p < 0.05 and candidate mean is strictly higher
        if pval is not None and pval < alpha_threshold and diff_mean > 0.0:
            summary.is_statistically_significant = True

    return summary
