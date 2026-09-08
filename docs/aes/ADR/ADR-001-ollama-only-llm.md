# ADR-001: Ollama-Only Local LLM for Experiment Scientist

## Status
Accepted

## Context
The Self-Healing RAG pipeline is designed to operate locally without mandatory external cloud API keys, utilizing Ollama (`mistral:7b` by default). The Autonomous Experiment Scientist requires an LLM to formulate hypotheses, analyze trial trends, and recommend candidate configurations.

## Decision
We mandate local Ollama as the primary LLM provider for the Autonomous Experiment Scientist. All prompts must be structured to elicit strict JSON adhering to Pydantic schemas. If external OpenAI keys are optionally provided in settings, they may be utilized, but the system must function end-to-end using Ollama alone.

## Consequences
- **Positive:** Zero cloud API costs, no rate limits, full privacy for proprietary documents, and repeatable offline benchmarking.
- **Negative:** Local inference requires sufficient RAM/GPU and may produce malformed JSON more frequently than frontier commercial models.
- **Mitigation:** The deterministic engine includes structured JSON repair loops and automatic fallback to Bayesian/Random search if Ollama responses fail validation.
