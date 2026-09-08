# Autonomous Experiment Scientist (AES) - Implementation Roadmap

## 1. Phase Breakdown & Milestones

### Phase 0: Architecture & Research Documentation (Complete)
- Author comprehensive specifications in `docs/aes/`:
  - `PRD.md`, `ARCHITECTURE.md`, `SYSTEM_DESIGN.md`, `AGENT_DESIGN.md`
  - `EXPERIMENT_DESIGN.md`, `EVALUATION_PLAN.md`, `METRICS.md`
  - `CONFIGURATION_SPACE.md`, `SAFETY_AND_GUARDRAILS.md`, `DATA_MODEL.md`
  - `API_SPEC.md`, `UI_SPEC.md`, `OBSERVABILITY.md`, `TESTING_STRATEGY.md`
  - `EXPERIMENT_PROTOCOL.md`, `FAILURE_TAXONOMY.md`, `ADR/`, `EXPERIMENTS/`

### Phase 1: Deterministic Experimentation Foundation
- `backend/core/config.py`: Implement `Settings.with_overrides(**kwargs)`.
- `backend/graph/container.py`: Support `ServiceContainer.build(settings_override)`.
- `backend/graph/runner.py`: Add `skip_cache` and `skip_websocket` support.
- `backend/experiments/models.py`: Pydantic data schemas.
- `backend/experiments/config_registry.py`: Search space declaration and clamping.
- `backend/experiments/store.py`: Protocol and JSON implementation.
- `backend/experiments/statistics.py`: Bootstrap CIs and paired Wilcoxon test.
- `backend/experiments/metrics.py`: Metric computation and quality scoring.
- `backend/experiments/objective.py`: Multi-objective scoring and penalties.
- `backend/experiments/runner.py`: Pipeline execution and telemetry capture.

### Phase 2: Autonomous Scientist & Baselines
- `backend/experiments/baselines/`:
  - `default.py`: Baseline zero trial.
  - `random.py`: Uniform random search.
  - `grid.py`: Discretized grid search.
  - `bayesian.py`: Surrogate-guided adaptive search.
- `backend/experiments/scientist/`:
  - `prompt.py`: Structured prompt builder.
  - `agent.py`: Ollama-powered hypothesis generator with deterministic fallback.
  - `retrospective.py`: Scientific synthesis and report generation.

### Phase 3: Benchmarks & Vector Isolation
- `data/eval/dataset_v1.json`: 20 golden evaluation samples.
- `data/eval/dataset_v2_candidates.json`: Synthetic candidate queries with review flags.
- `scripts/aes/precompute_chunks.py`: Pre-indexer for collections `c500_o50`, `c700_o100`, `c1500_o300`.

### Phase 4: CLI & Integration Verification
- `backend/experiments/cli.py`: CLI commands (`run`, `baselines`, `report`, `status`).
- Comprehensive unit and integration test suite verification.
