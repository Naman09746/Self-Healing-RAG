# Autonomous Experiment Scientist (AES) - Failure Taxonomy & Mitigation

## 1. Failure Categories
During autonomous experimentation, failures can occur at various stages of reasoning, orchestration, retrieval, generation, and evaluation. This taxonomy defines the recognized error states, root causes, and deterministic mitigations:

| Error Code | Category | Symptom / Description | Engine Mitigation Action |
|---|---|---|---|
| `ERR_INVALID_PARAM_SCHEMA` | Scientist Reasoning | Scientist outputs non-existent parameter name or unsupported type. | Parse failure message, send correction prompt to LLM (up to 2 retries); fallback to Bayesian/Random search. |
| `ERR_PARAM_OUT_OF_BOUNDS` | Validation | Scientist requests parameter outside valid range (e.g., `top_k=50`). | Deterministic clamping to declared upper/lower bound; log warning. |
| `ERR_QUERY_TIMEOUT` | Execution | Pipeline takes longer than `query_timeout_seconds` (30s). | Abort query execution; assign 0 quality score and max penalty for that query; continue trial. |
| `ERR_LLM_PROVIDER_DOWN` | Infrastructure | Ollama connection refused or times out. | Retry with exponential backoff (3 attempts); switch to deterministic Bayesian sampler for parameter selection. |
| `ERR_CIRCUIT_BREAKER_TRIPPED`| Safety | 3 consecutive trials crash or fail all queries. | Immediately halt campaign, flush store checkpoint to disk, emit alert to user. |
| `ERR_MISSING_COLLECTION` | Data / Storage | Pre-computed collection not found (e.g. `rag_collection_c1500_o300`). | Fallback to default `rag_collection` with warning; do not mutate vector store. |
| `ERR_SYNTHETIC_DATA_LEAK` | Dataset Integrity | Candidate dataset contains unlabeled or unverified samples. | Enforce `status == 'verified'` filter unless `--include-unverified-candidates` flag is explicitly enabled. |
| `ERR_SAMPLE_VARIANCE_HIGH` | Statistical Rigor | Score delta has $p \ge 0.05$ or confidence interval crosses zero. | Flag recommendation as "statistically inconclusive"; prevent deployment recommendation. |
