# Experiment Campaign: [Campaign Name / ID]

- **Date:** YYYY-MM-DD
- **Objective:** [Optimization Objective Description]
- **Target Metrics:** Quality vs. Latency vs. Cost vs. Healing
- **Evaluation Dataset:** `dataset_v1` (N = 20)
- **Baseline Strategy:** [e.g. Default vs. Ollama Scientist]

## 1. Initial Baseline Performance (Trial 0)
- **Composite Quality Score:** 0.000 (95% CI: [0.000, 0.000])
- **p95 Latency:** 0.0 ms
- **Mean Cost / Query:** $0.000
- **Mean Healing Count:** 0.0

## 2. Iteration History & Hypotheses
| Trial | Hypothesis | Tested Parameters | Quality | p95 Latency | Wilcoxon $p$-val | Significant? |
|---|---|---|---|---|---|---|
| 0 | Default baseline | `top_k=5, alpha=0.5` | ... | ... | N/A | N/A |
| 1 | Increase hybrid alpha | `alpha=0.75` | ... | ... | ... | ... |

## 3. Findings & Retrospective
- **Key Insight:** [What did we learn about parameter sensitivity?]
- **Optimal Configuration Identified:**
  ```json
  {
    "top_k": 7,
    "hybrid_search_alpha": 0.65,
    "rerank_threshold": 0.2
  }
  ```
- **Deployment Recommendation:** [Promote / Reject with statistical justification]
