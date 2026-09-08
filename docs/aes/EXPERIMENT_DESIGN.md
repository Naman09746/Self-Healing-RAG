# Autonomous Experiment Scientist (AES) - Experiment Design

## 1. Experiment Life Cycle
An experiment campaign is a bounded, reproducible investigation containing one or more experimental trials.

```
Campaign Initialization
   │
   ├─► 1. Establish Default Baseline (Trial 0)
   │      - Run production settings across evaluation dataset
   │      - Compute reference score, p95 latency, cost, and per-query metric vectors
   │
   ├─► 2. Iterative Experimentation Loop (Trial 1 .. N)
   │      - Select candidate config (via Scientist or Baseline Strategy)
   │      - Validate against Parameter Search Space constraints
   │      - Execute pipeline with overrides (bypassing caches)
   │      - Record per-query quality metrics, latency, token costs, healing counts
   │      - Calculate mean, std, 95% bootstrap CIs
   │      - Execute Paired Wilcoxon Signed-Rank Test against Trial 0
   │      - Evaluate Objective Function & update Pareto frontier
   │
   └─► 3. Campaign Finalization
          - Identify Best Overall Configuration
          - Generate Statistical Significance Report
          - Produce Markdown Retrospective & Leaderboard
```

## 2. Baseline Comparison Strategies
To evaluate whether the Autonomous Scientist genuinely adds value over heuristic approaches, AES implements four standard baseline strategies:

1. **Default Config:** The frozen production configuration. Used as the anchor for paired comparisons and effect size calculations.
2. **Random Search:** Uniformly samples candidate values from each parameter's defined range. Serves as the null hypothesis for optimization efficiency.
3. **Grid Search:** Systematically tests the full cartesian product of a pre-selected subset of key parameters (e.g., $k \in \{3, 5, 8\}$, $\alpha \in \{0.3, 0.5, 0.7\}$).
4. **Bayesian / Adaptive Search:** Fits a surrogate probabilistic model (Gaussian Process or TPE via `scipy.optimize` / Parzen estimators) modeling $P(\text{Score} \mid \theta)$ to trade off exploration and exploitation.

## 3. Pre-computed Chunk Collections
Because re-indexing large corpora during an experiment is time-consuming and computationally expensive, AES pre-indexes distinct chunking configurations into dedicated ChromaDB collections:

| Collection Name | Chunk Size | Chunk Overlap | Use Case |
|---|---|---|---|
| `rag_collection_c500_o50` | 500 tokens | 50 tokens | Granular, dense context retrieval |
| `rag_collection_c700_o100` | 700 tokens | 100 tokens | Standard production balance |
| `rag_collection_c1500_o300` | 1500 tokens | 300 tokens | Broad, multi-paragraph document context |

When the Scientist or baseline explores different chunk sizes, the engine routes retrieval to the corresponding pre-computed collection without performing any runtime disk writes or vector re-indexing.
