# Autonomous Experiment Scientist (AES) - Testing Strategy

## 1. Testing Philosophy
The testing strategy guarantees that:
1. The autonomous layer never breaks existing RAG capabilities.
2. The statistical engine is mathematically correct (unit tested against known distributions).
3. The budget and safety guardrails are unbypassable.
4. Experiment persistence and recovery function reliably across process restarts.

## 2. Test Suites

### 2.1 Unit Tests (`backend/tests/unit/`)
- **`test_experiment_models.py`:** Tests Pydantic validation, serialization, clamping rules, and schema checks for `ObjectiveConfig`, `BudgetConfig`, and `CandidateProposal`.
- **`test_search_space.py`:** Tests parsing of `search_space.yaml`, default value extraction, bounds checking, and collection mapping.
- **`test_statistics.py`:** Tests mean, standard error, 95% bootstrap confidence interval calculation, and paired Wilcoxon test against synthetic known vectors.
- **`test_objective.py`:** Tests score compilation, penalty deductions, and edge conditions (zero latency, zero healing).
- **`test_store.py`:** Tests `ExperimentStore` operations: create campaign, log trial, update checkpoint, query leaderboard, and persist to JSON.
- **`test_budget_enforcement.py`:** Tests max runs, wall-clock timeout triggering, query timeout handling, and circuit breaker trip conditions.

### 2.2 Integration Tests (`backend/tests/integration/`)
- **`test_experiment_runner.py`:** Executes mock pipeline runs with settings overrides, confirming that `ServiceContainer` is cleanly rebuilt and cache is bypassed.
- **`test_baseline_strategies.py`:** Verifies that Default, Random, Grid, and Bayesian strategies generate valid, clamped parameter configurations.
- **`test_scientist_loop.py`:** Validates Scientist prompt formatting, JSON response parsing, and error-recovery fallback when LLM output is malformed.
