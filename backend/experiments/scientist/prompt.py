from typing import List, Optional
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.models import ObjectiveConfig, TrialResult


def build_scientist_system_prompt() -> str:
    return (
        "You are the Autonomous Experiment Scientist (AES) optimizing a production Self-Healing RAG pipeline.\n"
        "Your mission is to formulate rigorous, testable hypotheses and propose parameter configurations that maximize the target objective.\n"
        "You reason systematically about retrieval mechanics, context precision, latency trade-offs, and self-healing behaviors.\n"
        "Always output valid, well-formed JSON conforming precisely to the requested schema. Do NOT include markdown code fences or commentary outside the JSON."
    )


def format_trial_history_table(trials: List[TrialResult]) -> str:
    if not trials:
        return "No prior trials recorded yet. This will be the first experimental configuration."

    lines = [
        "| Trial | Strategy | Parameters | Score | Quality (95% CI) | p95 Latency | Healing | Significant? |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for t in trials:
        p_str = ", ".join(f"{k}={v}" for k, v in t.parameters.items() if k in ("top_k", "hybrid_search_alpha", "rerank_threshold", "chunk_variant"))
        ci_str = f"[{t.statistical_summary.ci_lower_95:.2f}, {t.statistical_summary.ci_upper_95:.2f}]" if t.statistical_summary else "N/A"
        sig_str = "YES" if (t.statistical_summary and t.statistical_summary.is_statistically_significant) else "NO"
        lines.append(
            f"| #{t.trial_number} | {t.strategy.value} | {p_str} | {t.objective_score:.3f} | {t.mean_quality:.3f} {ci_str} | {t.p95_latency_ms:.0f}ms | {t.mean_healing_count:.1f} | {sig_str} |"
        )

    return "\n".join(lines)


def build_proposal_prompt(
    objective: ObjectiveConfig,
    registry: ConfigRegistry,
    trials: List[TrialResult],
    best_trial: Optional[TrialResult] = None,
) -> str:
    schema_desc = registry.get_schema_summary()
    history_table = format_trial_history_table(trials)

    best_desc = "None"
    if best_trial:
        best_desc = f"Trial #{best_trial.trial_number} (Score: {best_trial.objective_score:.3f}, Quality: {best_trial.mean_quality:.3f}, p95: {best_trial.p95_latency_ms:.0f}ms) with parameters: {best_trial.parameters}"

    return f"""### OPTIMIZATION OBJECTIVE
Name: {objective.name}
Description: {objective.description}
Max p95 Latency SLA: {objective.max_p95_latency_ms} ms
Weights: Faithfulness={objective.weights.faithfulness}, Relevance={objective.weights.answer_relevance}, Precision={objective.weights.context_precision}, Recall={objective.weights.context_recall}

### SEARCH SPACE SPECIFICATION
{schema_desc}

### BEST TRIAL IDENTIFIED SO FAR
{best_desc}

### TRIAL EXECUTION HISTORY
{history_table}

### INSTRUCTIONS
1. Analyze the performance trends, quality deltas, and latency trade-offs observed across completed trials.
2. Formulate a specific, falsifiable hypothesis predicting how adjusting one or more parameters will improve the objective score.
3. Propose the next candidate parameters dictionary.

You MUST respond strictly with a valid JSON object matching this schema:
{{
  "hypothesis": "Clear explanation of what you are testing and the theoretical RAG mechanism",
  "expected_outcome": "Expected directional impact on quality (+/-), latency (+/- ms), and cost",
  "parameters": {{
    "top_k": 5,
    "hybrid_search_alpha": 0.65,
    "rerank_threshold": 0.2,
    "routing_confidence_threshold": 0.6,
    "healing_max_retries": 2,
    "chunk_variant": "c700_o100"
  }},
  "justification": "Detailed scientific rationale referencing previous trial results and trade-offs"
}}"""
