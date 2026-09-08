# Autonomous Experiment Scientist (AES) - Safety, Guardrails & Budgets

## 1. Safety Principles
The Autonomous Experiment Scientist must never compromise the availability, performance, or data integrity of the host Self-Healing RAG system. The following guardrails are enforced at the code level:

## 2. Hard Budget Enforcement
Every experiment campaign is governed by a `BudgetConfig` enforced by the deterministic engine:
- **`max_experiments`:** Hard upper bound on trials executed (default: 10). The runner immediately stops when this limit is reached.
- **`max_total_seconds`:** Global wall-clock timeout for the entire campaign (default: 3600 seconds). If exceeded mid-trial, the running trial completes gracefully and no further trials are started.
- **`query_timeout_seconds`:** Maximum duration allocated to a single query execution in LangGraph (default: 30 seconds). Timed-out queries record a timeout failure and default to 0 quality score.
- **`max_tokens_budget`:** Maximum cumulative LLM tokens across the campaign (default: 500,000 tokens).

## 3. Circuit Breaker Mechanism
To prevent runaway loops from crashing servers or wasting resources:
- **`max_consecutive_failures`:** If 3 consecutive trials throw unhandled exceptions or return zero valid results, the campaign circuit breaker trips:
  - The campaign status transitions to `FAILED_CIRCUIT_BREAKER`.
  - An emergency checkpoint is saved.
  - The user is notified with the exact traceback of the failure trigger.

## 4. Vector Store Isolation Guarantees
- **No In-Place Modification:** The engine NEVER performs `delete_collection`, `upsert`, or `reset` on production collections (`rag_collection`).
- **Pre-computed Collection Fallback:** If a pre-computed collection (`rag_collection_c500_o50`, etc.) is missing, the engine falls back to the base collection and records a warning in the experiment metadata.
- **Sandboxed Scratch Dirs:** Temporary files and scratch vector indices created for experimental data are confined to `.tmp_experiments/` and guaranteed to be deleted in a `finally:` block.
