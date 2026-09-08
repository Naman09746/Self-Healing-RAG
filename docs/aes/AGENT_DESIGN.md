# Autonomous Experiment Scientist (AES) - Agent Design

## 1. Role Definition & Scope
The Autonomous Scientist is an LLM-driven research agent whose role is strictly **advisory and analytical**. It acts as a thoughtful experiment designer, interpreting multi-objective goals and drawing deductions from empirical trial data.

To prevent unpredictability, hallucinated parameter ranges, and budget violations:
- The Scientist **does not** execute code or shell commands directly.
- The Scientist **does not** modify the database or file system directly.
- The Scientist communicates via structured JSON requests and responses parsed and validated by Pydantic models.

## 2. Scientist Reasoning Cycle
For each experiment iteration, the Scientist executes a 4-stage cognitive loop:

1. **Context Ingestion:**
   - Evaluates the overarching Objective (e.g., target metrics, SLA constraints).
   - Reviews the Parameter Schema (allowed parameter names, types, and valid bounds).
   - Inspects the Historical Trials Table (past configurations, observed scores, p95 latencies, cost, healing events, and statistical confidence intervals).
2. **Hypothesis Formulation:**
   - Analyzes trends (e.g., *"Trial 3 increased hybrid_alpha to 0.8 which improved precision by +0.06, but increased healing retries; perhaps increasing rerank_threshold will prune noisy chunks while preserving precision."*).
   - Formulates a testable, falsifiable scientific hypothesis.
3. **Candidate Proposal:**
   - Outputs a concrete dictionary of parameter overrides.
   - Specifies the anticipated directional effect on each objective metric.
4. **Post-Trial Reflection:**
   - Given the empirical results from the deterministic engine, the Scientist compares the observed outcome against its prior hypothesis, updating its internal mental model for subsequent iterations.

## 3. Structured Prompt Architecture
The Scientist is prompted with strict JSON schemas and system rules:

```
You are the Autonomous Experiment Scientist for a Self-Healing RAG pipeline.
Your objective is: {objective_description}

You have access to the following parameter search space:
{search_space_schema}

History of completed trials:
{trial_history_summary}

Best configuration found so far:
{best_trial_summary}

Respond ONLY with valid JSON matching this schema:
{
  "hypothesis": "Clear explanation of what change you are testing and why",
  "expected_outcome": "Directional impact on quality, latency, or cost",
  "parameters": {
    "key": value
  },
  "justification": "Detailed scientific rationale referencing previous trial results"
}
```

## 4. Fallback and Deterministic Recovery
If the LLM generates invalid JSON, specifies out-of-bounds parameters, or times out:
1. **Schema Correction:** The engine sends back the validation error to the LLM (up to 2 retries).
2. **Deterministic Fallback:** If the LLM repeatedly fails or if Ollama is unreachable, the engine automatically falls back to the **Bayesian / Adaptive Search** sampler or **Random Sampler**, ensuring the optimization campaign never crashes or hangs.
