# Autonomous Experiment Scientist (AES) - Experiment Protocol

## 1. Standard Experimentation Protocol (SEP)
To ensure scientific rigor, reproducibility, and prevent p-hacking or accidental regressions, all experimentation campaigns executed by AES follow this 5-stage protocol:

### Stage 1: Hypothesis Formulation & Registration
- Before evaluating any candidate parameters, a falsifiable hypothesis must be registered in the experiment log:
  - *Independent Variable(s):* Specified configuration parameters being adjusted.
  - *Dependent Variable(s):* Targeted metrics expected to change (e.g. `context_precision`, `p95_latency_ms`).
  - *Anticipated Direction:* Predicted sign and mechanism of change.

### Stage 2: Baseline Benchmark Anchor
- The default system configuration ($\theta_0$) must be evaluated on the identical versioned evaluation dataset (`dataset_v1@sha256`) to establish the baseline performance distribution.
- All subsequent trials compute paired per-query deltas: $\Delta Q_i = Q_i(\theta_k) - Q_i(\theta_0)$.

### Stage 3: Controlled Execution
- Pipeline execution must bypass cache layers (`skip_cache=True`) to prevent hit-rate distortion.
- Re-indexing tests must query designated pre-computed collections, guaranteeing identical document contents.
- Resource limits (timeouts, token limits) are strictly enforced.

### Stage 4: Statistical Significance Audit
- Compute mean, standard deviation, median, and 95% bootstrap confidence intervals.
- Perform a two-tailed Paired Wilcoxon Signed-Rank Test.
- Criteria for claiming an optimization improvement:
  1. Mean objective score strictly exceeds the baseline: $\bar{S}(\theta_k) > \bar{S}(\theta_0)$.
  2. The quality difference is statistically significant ($p < 0.05$).
  3. p95 latency does not breach the specified SLA threshold.

### Stage 5: Post-Trial Retrospective & Archival
- Capture full telemetry, prompt snapshots, and metrics in `ExperimentStore`.
- Update the trial leaderboard and Pareto frontier.
- Generate human-readable Markdown retrospective detailing findings.
