# Autonomous Experiment Scientist (AES) - Observability Specification

## 1. Metrics & Instrumentation
AES extends the existing OpenTelemetry and Prometheus observability stack of the Self-Healing RAG pipeline with experiment-specific instrumentation:

### Prometheus Metrics
- `aes_campaigns_total{status}`: Counter tracking initiated, succeeded, and aborted campaigns.
- `aes_trials_total{strategy, status}`: Counter tracking trials across strategies (`default`, `random`, `grid`, `bayesian`, `scientist`).
- `aes_trial_duration_seconds{strategy}`: Histogram recording trial execution duration.
- `aes_query_quality_score{strategy, metric}`: Gauge tracking running quality scores per metric type.
- `aes_circuit_breaker_trips_total`: Counter tracking consecutive error trips.

### OpenTelemetry Tracing
- Root Span: `aes.campaign` (encompasses full campaign lifecycle).
- Child Spans:
  - `aes.trial` (attributes: `trial_id`, `strategy`, `trial_number`, `parameters.*`).
  - `aes.scientist.propose` (measures Ollama Scientist prompt latency and response validity).
  - `aes.query_eval` (measures individual pipeline query execution and evaluator scoring).
  - `aes.stats.significance` (records bootstrap resampling and Wilcoxon test compute time).

## 2. Structured Logging
AES utilizes `structlog` to emit JSON-formatted logs for automated ingestion:
- Event: `aes.trial.started`
- Event: `aes.trial.completed` (includes composite score, latency percentiles, Wilcoxon p-value)
- Event: `aes.circuit_breaker.triggered` (includes consecutive failure count and error traceback)
- Event: `aes.campaign.finalized` (includes best trial metadata and summary of tested hypotheses)
