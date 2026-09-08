# Autonomous Experiment Scientist (AES) - Data Model Specification

## 1. Entity Overview
The AES data model captures campaigns, individual experiment trials, per-query telemetry, statistical evaluations, and scientific hypotheses.

```mermaid
erDiagram
    CAMPAIGN ||--o{ TRIAL : contains
    CAMPAIGN ||--|| OBJECTIVE : targets
    CAMPAIGN ||--|| BUDGET : constrained_by
    TRIAL ||--o{ TRIAL_QUERY_RESULT : produces
    TRIAL ||--|| STATISTICAL_SUMMARY : evaluates
    TRIAL ||--|| HYPOTHESIS : tests

    CAMPAIGN {
        string campaign_id PK
        string name
        string status
        string baseline_strategy
        datetime created_at
        datetime updated_at
    }

    TRIAL {
        string trial_id PK
        string campaign_id FK
        int trial_number
        json parameters
        float objective_score
        float mean_quality
        float p95_latency_ms
        int total_tokens
        int healing_retries
        string status
    }

    TRIAL_QUERY_RESULT {
        string query_id
        string query_text
        string generated_answer
        float faithfulness
        float relevance
        float precision
        float recall
        float latency_ms
        int healing_count
    }

    STATISTICAL_SUMMARY {
        float mean
        float std_dev
        float median
        float ci_lower_95
        float ci_upper_95
        float wilcoxon_p_value
        boolean is_statistically_significant
    }
```

## 2. Pydantic Schemas (Code Representation)
The core entities map directly to Pydantic v2 schemas in `backend/experiments/models.py`:
- `ObjectiveConfig`: Definition of weights, constraints, and latency targets.
- `BudgetConfig`: Resource caps, timeout limits, and circuit breakers.
- `CandidateProposal`: Structured hypothesis, parameter dictionary, and reasoning from the Scientist.
- `TrialQueryResult`: Fine-grained result of a single query in a trial.
- `StatisticalSummary`: Bootstrap confidence intervals and paired test metrics.
- `TrialResult`: Complete trial execution snapshot.
- `Campaign`: Top-level campaign container and trial leaderboard.
