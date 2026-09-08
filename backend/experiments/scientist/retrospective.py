from typing import List, Optional
from backend.experiments.models import Campaign, TrialResult


class RetrospectiveGenerator:
    """Generates structured scientific markdown reports summarizing campaign outcomes."""

    @classmethod
    def generate_markdown_report(cls, campaign: Campaign) -> str:
        trials = sorted(campaign.trials, key=lambda t: t.objective_score, reverse=True)
        baseline_trial = next((t for t in campaign.trials if t.trial_number == 0), None)
        best_trial = next((t for t in campaign.trials if t.trial_id == campaign.best_trial_id), trials[0] if trials else None)

        report = [
            f"# AES Scientific Retrospective: {campaign.name}",
            f"\n- **Campaign ID:** `{campaign.campaign_id}`",
            f"- **Status:** `{campaign.status.value}`",
            f"- **Optimization Strategy:** `{campaign.baseline_strategy.value}`",
            f"- **Benchmark Dataset:** `{campaign.dataset_version}`",
            f"- **Total Trials Executed:** {len(campaign.trials)}",
            f"- **Max p95 Latency SLA:** {campaign.objective.max_p95_latency_ms:.0f} ms",
            "\n## 1. Executive Summary",
        ]

        if best_trial and baseline_trial:
            quality_delta = best_trial.mean_quality - baseline_trial.mean_quality
            latency_delta = best_trial.p95_latency_ms - baseline_trial.p95_latency_ms
            report.append(
                f"The campaign evaluated {len(campaign.trials)} configurations. "
                f"The optimal configuration was identified in **Trial #{best_trial.trial_number}** ({best_trial.strategy.value}).\n\n"
                f"- **Baseline (Trial 0) Score:** {baseline_trial.objective_score:.4f} (Quality: {baseline_trial.mean_quality:.4f}, p95: {baseline_trial.p95_latency_ms:.0f}ms)\n"
                f"- **Optimal (Trial #{best_trial.trial_number}) Score:** {best_trial.objective_score:.4f} (Quality: {best_trial.mean_quality:.4f}, p95: {best_trial.p95_latency_ms:.0f}ms)\n"
                f"- **Quality Improvement:** {'+' if quality_delta >= 0 else ''}{quality_delta:.4f}\n"
                f"- **Latency Change:** {'+' if latency_delta >= 0 else ''}{latency_delta:.0f} ms\n"
            )
        elif best_trial:
            report.append(
                f"The best configuration achieved an objective score of **{best_trial.objective_score:.4f}** "
                f"(Quality: {best_trial.mean_quality:.4f}, p95 Latency: {best_trial.p95_latency_ms:.0f}ms).\n"
            )

        # Statistical Significance Section
        report.append("## 2. Statistical Significance Analysis")
        if best_trial and best_trial.statistical_summary:
            stats = best_trial.statistical_summary
            sig_text = "**STATISTICALLY SIGNIFICANT**" if stats.is_statistically_significant else "*INCONCLUSIVE (insufficient statistical power)*"
            report.append(
                f"- **Sample Size:** {stats.sample_size} queries\n"
                f"- **95% Bootstrap Confidence Interval:** `[{stats.ci_lower_95:.4f}, {stats.ci_upper_95:.4f}]`\n"
                f"- **Paired Wilcoxon Signed-Rank p-value:** `{stats.wilcoxon_p_value if stats.wilcoxon_p_value is not None else 'N/A'}`\n"
                f"- **Effect Size (Cohen's d):** `{stats.effect_size if stats.effect_size is not None else 'N/A'}`\n"
                f"- **Significance Verdict ($p < 0.05$):** {sig_text}\n"
            )

        # Trial Leaderboard
        report.append("## 3. Trial Leaderboard (Ranked by Objective Score)")
        report.append(
            "| Rank | Trial | Strategy | Parameters | Score | Quality | p95 Latency | Healing | Significant? |\n"
            "|---|---|---|---|---|---|---|---|---|"
        )
        for rank, t in enumerate(trials, start=1):
            param_summary = ", ".join(f"{k}={v}" for k, v in t.parameters.items() if k in ("top_k", "hybrid_search_alpha", "rerank_threshold", "chunk_variant"))
            sig = "YES" if (t.statistical_summary and t.statistical_summary.is_statistically_significant) else "NO"
            report.append(
                f"| #{rank} | #{t.trial_number} ({t.trial_id[:8]}) | {t.strategy.value} | {param_summary} | **{t.objective_score:.4f}** | {t.mean_quality:.4f} | {t.p95_latency_ms:.0f}ms | {t.mean_healing_count:.1f} | {sig} |"
            )

        # Optimal Parameters Recommendation
        report.append("\n## 4. Production Deployment Recommendation")
        if best_trial:
            report.append(
                f"Recommended configuration settings for production deployment:\n"
                "```json\n"
                f"{best_trial.parameters}\n"
                "```\n"
            )
            if best_trial.hypothesis:
                report.append(f"**Scientist Hypothesis:**\n> {best_trial.hypothesis}\n")
            if best_trial.justification:
                report.append(f"**Scientific Justification:**\n> {best_trial.justification}\n")

        return "\n".join(report)
