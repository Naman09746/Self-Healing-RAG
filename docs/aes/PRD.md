# Autonomous Experiment Scientist (AES) - Product Requirements Document (PRD)

## 1. Executive Summary
The Autonomous Experiment Scientist (AES) is an intelligent optimization and experimentation layer built natively on top of the Self-Healing RAG multi-agent architecture. Its mission is to transform manual parameter tuning into a systematic, hypothesis-driven, statistically rigorous autonomous research process.

Given a high-level optimization objective (e.g., *"Optimize this RAG system for maximum answer quality while keeping p95 latency below 2000ms and minimizing cost"*), the AES autonomously formulates scientific hypotheses, plans targeted experimentation campaigns, tests candidate configurations across versioned benchmark datasets, measures performance with paired statistical tests, compares against baseline strategies, and recommends optimal configurations without risking production stability.

## 2. Problems Addressed
1. **Manual Guess-and-Check Tuning:** Engineers typically hand-tweak `top_k`, chunk sizes, reranking thresholds, and prompts without systematic hypothesis generation or isolation.
2. **Lack of Statistical Rigor:** RAG optimization often claims improvements based on trivial score differences across small sample sizes without confidence intervals, standard errors, or paired non-parametric significance testing.
3. **Absence of Systematic Baselines:** Teams cannot readily verify if an LLM-driven tuning agent outperforms simple random search, grid search, or Bayesian optimization.
4. **Data Contamination & Drift:** Evaluating against synthetic datasets without golden ground-truth splits leads to overfitting and degraded production accuracy.
5. **Operational Risk:** Modifying production vector stores, live indices, or active caches during experiments causes regressions and downtime.

## 3. Goals & Non-Goals
### 3.1 Primary Goals
- **Autonomous Multi-Objective Optimization:** Optimize compound objectives balancing quality (faithfulness, answer relevance, context precision/recall), p95 latency, simulated token cost, and self-healing trigger rates.
- **Statistical Significance Engine:** Every recommendation must report mean, standard deviation, 95% bootstrap confidence intervals, and paired Wilcoxon signed-rank test results against the baseline.
- **Scientist vs. Engine Separation:** LLM Scientist generates hypotheses, plans, and scientific retrospectives; deterministic code strictly enforces validation, execution, budget caps, circuit breakers, and persistence.
- **Baseline Comparative Suite:** Built-in execution of Default Config, Random Search, Grid Search, and Bayesian (GP/TPE) search strategies to benchmark Scientist value-add.
- **Non-Destructive Hybrid Isolation:** Read-only access to existing production vector stores for retrieval parameter sweeps; dedicated isolated collections for re-indexing sweeps.
- **Hard Safety & Budget Guardrails:** Enforce max run count, token budgets, elapsed wall-clock limits, timeout per query, and consecutive error circuit-breakers.

### 3.2 Non-Goals
- Replacing the core LangGraph self-healing architecture.
- Real-time online A/B testing on live production user traffic (AES is offline/staging benchmark-driven).
- Cloud-only proprietary API dependencies (AES must function with local Ollama `mistral:7b`).

## 4. User Personas & Use Cases
- **Persona 1: RAG Platform Engineer:** Wants to evaluate whether switching chunking from 500 to 700 tokens or adjusting hybrid retrieval alpha improves context precision without exceeding latency SLAs.
- **Persona 2: ML Research Scientist:** Wants to benchmark agentic reasoning strategies (Ollama Scientist vs. Bayesian optimization) on question answering accuracy across domain-specific corpora.
- **Persona 3: Production Tech Lead:** Needs an audit trail and markdown scientific report demonstrating statistical significance before approving configuration changes in production.

## 5. System Requirements
- **Hardware/Runtime:** Python 3.10+, Ollama local inference server, ChromaDB vector store.
- **Determinism:** Fixed random seeds for baseline samplers, frozen benchmark datasets, read-only collection isolation.
- **Reproducibility:** Every experiment run captures full git commit hash, configuration snapshot, dataset version, execution logs, and raw evaluation telemetry.
