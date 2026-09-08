# Autonomous Experiment Scientist (AES) - System Architecture

## 1. Architectural Philosophy: The Scientist vs. Engine Boundary
A foundational design principle of AES is the strict boundary between **Autonomous Reasoning** (the LLM Scientist) and **Deterministic Execution** (the Experiment Engine):

```
+-------------------------------------------------------------------------+
|                         AES CLI / API Layer                             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  LLM Autonomous Scientist (Advisory)                     |
|  - Parses high-level natural language objective                         |
|  - Inspects parameter schema & prior trial history                      |
|  - Formulates scientific hypotheses & suggests candidate config         |
|  - Generates post-run analytical retrospectives & markdown reports      |
+-------------------------------------------------------------------------+
                                    |  Candidate Proposal
                                    v
+-------------------------------------------------------------------------+
|               Deterministic Experiment Engine (Authoritative)           |
|  - Parameter Schema Validation & Range Clamping                         |
|  - Budget & Resource Enforcement (Max Runs, Timeouts, Tokens)           |
|  - Circuit Breakers (consecutive error thresholds)                      |
|  - Baseline Search Strategies (Default, Random, Grid, Bayesian/TPE)     |
|  - Read-only & Isolated Pre-computed Collection Routing                 |
|  - Parallel / Batch Runner without mutating global Settings             |
|  - Metric Aggregator & Statistical Significance Engine                  |
|  - ExperimentStore Persistence (JSON / SQLite / PostgreSQL)             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|               Existing Self-Healing RAG Pipeline (Runtime)              |
|  - ServiceContainer.build(settings_override)                            |
|  - LangGraph 8-Node State Machine (Routing, Retrieval, Grading, Eval)   |
|  - ChromaDB Vector Store & BM25 Hybrid Retriever                        |
|  - RAGASEvaluator / Fallback Heuristic Evaluator                        |
+-------------------------------------------------------------------------+
```

## 2. Core Subsystems

### 2.1 Configuration Registry & Search Space
Defines mutable parameters, data types, search bounds, step sizes, and safety constraints.
- Parameters are divided into:
  - **Read-Only Parameters** (e.g., `top_k`, `hybrid_search_alpha`, `rerank_threshold`, `routing_confidence_threshold`, `healing_max_retries`).
  - **Index-Variant Parameters** (e.g., `chunk_size`, `chunk_overlap`), routed to pre-indexed ChromaDB collections (`rag_collection_c500_o50`, `rag_collection_c700_o100`, `rag_collection_c1500_o300`).

### 2.2 Objective & Scoring Engine
Compiles natural language objectives into executable scalar scoring functions:
$$\text{Score} = w_q \cdot Q - w_l \cdot \text{Penalty}_{\text{p95}} - w_c \cdot \text{Penalty}_{\text{cost}} - w_h \cdot \text{Penalty}_{\text{healing}}$$
Where:
- $Q$ is composite answer quality (faithfulness, relevance, context recall).
- Latency SLA penalties penalize p95 response time beyond defined bounds.
- Token cost and healing rate penalties drive lean, efficient executions.

### 2.3 Statistical Engine
Eliminates false-positive wins through rigorous statistical testing:
- Calculates mean, variance, standard error, and median.
- Computes **95% Bootstrap Confidence Intervals** (1000 resamples).
- Executes **Paired Wilcoxon Signed-Rank Test** against the default baseline on identical question sets.
- Asserts a minimum statistical power ($p < 0.05$ and effect size threshold) before declaring a configuration superior.

### 2.4 Baseline Comparison Engine
AES provides automated baseline executors to establish benchmark standards:
1. **Default Baseline:** Unmodified production settings.
2. **Random Search:** Uniformly samples valid configurations across the bounded search space.
3. **Grid Search:** Evaluates cartesian product of critical discretised hyper-parameters.
4. **Bayesian / Adaptive Search:** Fits a surrogate Gaussian Process or Tree-structured Parzen Estimator (TPE) over trial histories.
5. **LLM Scientist:** Evaluates hypothesis-driven reasoning against the baselines on identical budgets.

### 2.5 Hybrid Vector Store Isolation
To guarantee safety and prevent corruption:
- Production collections (`rag_collection`) are opened with read-only client connections during parameter sweeps.
- Re-indexing experiments read from pre-computed static collections containing distinct chunking strategies.
- Transient scratch collections created for synthetic document tests are stored under isolated experiment-specific directories (`.chromadb_exp_<run_id>`) and automatically cleaned up on completion.
