# Autonomous Experiment Scientist (AES) - UI Specification

## 1. User Interface Overview
The AES provides both a rich terminal interface (via `rich` / Click CLI) and web-accessible dashboard views for tracking experimentation campaigns.

## 2. CLI Dashboard Views
The CLI provides three primary interactive display modes:
1. **Live Trial Progress (`aes run`):**
   - Real-time progress bar showing trial index, active candidate parameters, query progress (e.g., `Query [14/20]`), and elapsed execution time.
   - Status indicators for circuit-breaker health, token burn rate, and cache isolation.
2. **Experiment Leaderboard (`aes status`):**
   - Ranked tabular display of tested configurations sorted by objective score.
   - Columns: Rank, Trial ID, Strategy, Composite Quality, p95 Latency, Cost, Healing Count, Wilcoxon $p$-val, 95% CI.
3. **Statistical Deep-Dive (`aes report`):**
   - Paired comparison chart showing distribution shift of per-query quality deltas $(\Delta Q_i)$ relative to the default baseline.
   - Formal pass/fail indicator of statistical significance.

## 3. Web Dashboard Components (Optional UI Extension)
- **Campaign Configuration Modal:** Objective sliders (Quality vs. Latency vs. Cost), budget constraints, and strategy selector (Scientist vs. Random vs. Grid vs. Bayesian).
- **Interactive Pareto Frontier Scatter Plot:** X-axis = p95 Latency (ms), Y-axis = Composite Quality. Highlights dominant configurations on the convex hull.
- **Scientific Retrospective Viewer:** Formatted markdown viewer rendering hypothesis validation, parameter importance sensitivity charts, and production deployment recommendations.
