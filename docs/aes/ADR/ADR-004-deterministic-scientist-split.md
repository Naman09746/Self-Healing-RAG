# ADR-004: Strict Separation Between Reasoning Scientist and Deterministic Engine

## Status
Accepted

## Context
In agentic AI architectures, assigning both strategic reasoning (hypothesis formulation) and operational execution (running pipelines, checking timeouts, recording metrics, mutating databases) to an LLM agent leads to non-deterministic errors, tool-call hallucinations, resource leaks, and lack of reproducibility.

## Decision
We enforce a strict boundary:
- The **Autonomous Scientist** is strictly an **advisory** agent. It receives prompt contexts and outputs candidate hypotheses and parameter recommendations in JSON.
- The **Deterministic Engine** is strictly **authoritative**. It validates schemas, clamps parameter values, enforces trial budgets, halts on circuit breakers, calculates mathematical statistics, and manages database persistence.

## Consequences
- **Positive:** Zero chance of hallucinated parameters reaching production pipelines; absolute enforcement of resource limits; fully reproducible test runs.
- **Negative:** The Scientist cannot invent novel execution steps outside the predefined parameter and objective schemas.
