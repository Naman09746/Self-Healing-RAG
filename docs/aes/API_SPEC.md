# Autonomous Experiment Scientist (AES) - API Specification

## 1. REST Endpoints
AES provides programmatic access via FastAPI endpoints mounted under `/api/v1/experiments`:

### `POST /api/v1/experiments/campaigns`
Initiates a new experimentation campaign.
- **Request Body:**
  ```json
  {
    "name": "quality_latency_opt_v1",
    "objective": {
      "name": "balanced_quality_latency",
      "target_quality_metric": "composite_quality",
      "max_p95_latency_ms": 2000.0,
      "weights": {
        "faithfulness": 0.35,
        "answer_relevance": 0.25,
        "context_precision": 0.20,
        "context_recall": 0.20
      },
      "penalties": {
        "latency": 0.0005,
        "cost": 1.0,
        "healing": 0.05
      }
    },
    "budget": {
      "max_experiments": 10,
      "max_total_seconds": 3600,
      "query_timeout_seconds": 30,
      "max_consecutive_failures": 3
    },
    "baseline_strategy": "ollama_scientist"
  }
  ```
- **Response:** `201 Created` with Campaign metadata and assigned `campaign_id`.

### `GET /api/v1/experiments/campaigns/{campaign_id}`
Retrieves campaign progress, current trial, status, and trial leaderboard.

### `GET /api/v1/experiments/campaigns/{campaign_id}/report`
Generates and returns the scientific markdown retrospective and statistical significance breakdown.

### `POST /api/v1/experiments/campaigns/{campaign_id}/cancel`
Gracefully halts an ongoing campaign, ensuring checkpoints and store records are flushed.
