# Autonomous Experiment Scientist (AES) - Metrics & Mathematical Formulations

## 1. Quality Metrics
For each evaluated query $i \in \{1, \dots, N\}$:
- Faithfulness: $F_i \in [0, 1]$
- Answer Relevance: $R_i \in [0, 1]$
- Context Precision: $P_i \in [0, 1]$
- Context Recall: $C_i \in [0, 1]$

The aggregate quality score for trial $j$ is:
$$\bar{Q}_j = \frac{1}{N} \sum_{i=1}^N \left( w_f F_i + w_r R_i + w_p P_i + w_c C_i \right)$$
*(Default weights: $w_f = 0.35, w_r = 0.25, w_p = 0.20, w_c = 0.20$)*

## 2. Latency Percentiles
Latency per query is recorded in milliseconds: $\{L_1, \dots, L_N\}$.
- Mean latency: $\bar{L} = \frac{1}{N} \sum L_i$
- p95 latency: 95th percentile computed using linear interpolation between nearest ranks.

## 3. Objective Scoring Function
Objectives are defined as a constrained utility maximization problem:
$$\text{Score}(\theta) = \bar{Q}(\theta) - \lambda_{\text{lat}} \cdot \max(0, \text{p95}(\theta) - \tau_{\text{lat}}) - \lambda_{\text{cost}} \cdot \text{Cost}(\theta) - \lambda_{\text{heal}} \cdot \bar{H}(\theta)$$
Where:
- $\tau_{\text{lat}}$ is the p95 latency threshold SLA (e.g. 2000 ms).
- $\bar{H}(\theta)$ is the average number of self-healing retries per query.
- $\lambda$ are objective-specific penalty coefficients.

## 4. Statistical Significance Testing
### 4.1 Bootstrap Confidence Intervals
For any metric $M$, we generate $B = 1000$ bootstrap resamples $M^{*b}$ drawn with replacement from $\{M_1, \dots, M_N\}$:
$$\text{CI}_{95\%} = \left[ Q_{0.025}(M^*), Q_{0.975}(M^*) \right]$$

### 4.2 Paired Wilcoxon Signed-Rank Test
To compare candidate configuration $\theta_k$ against baseline $\theta_0$ across the exact same $N$ queries:
1. Compute pairwise differences $d_i = Q_i(\theta_k) - Q_i(\theta_0)$.
2. Exclude zero differences ($d_i = 0$).
3. Rank absolute differences $|d_i|$ from smallest to largest: $\text{rank}(|d_i|)$.
4. Compute test statistic $W = \min(W^+, W^-)$ where $W^+ = \sum_{d_i > 0} \text{rank}(|d_i|)$.
5. Obtain two-sided p-value:
   - If $p < 0.05$ and $\bar{d} > 0$, the candidate is declared **statistically superior**.
   - If $p \ge 0.05$, the difference is declared **statistically inconclusive** (insufficient evidence to claim improvement).
