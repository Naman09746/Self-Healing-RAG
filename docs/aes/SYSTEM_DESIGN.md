# Autonomous Experiment Scientist (AES) - System Design

## 1. Component Interactions and Workflow
The AES execution lifecycle proceeds through six structured stages:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as AES CLI / Orchestrator
    participant Sci as LLM Scientist
    participant Reg as Config & Space Registry
    participant Engine as Deterministic Engine
    participant Runner as Experiment Runner
    participant RAG as Self-Healing RAG Container
    participant Stats as Statistical Engine
    participant Store as ExperimentStore

    User->>CLI: run-campaign --objective "max quality, p95 < 2000ms"
    CLI->>Reg: Load Search Space & Base Config
    CLI->>Engine: Initialize Campaign (Budget, Max Runs, Seed)
    
    loop For each iteration until Budget Expended
        Engine->>Sci: Query Proposal (History, Search Space, Objective)
        Sci-->>Engine: Propose Candidate Config & Hypothesis
        Engine->>Reg: Validate & Clamp Candidate Config
        alt Validation Fails
            Engine->>Sci: Return Validation Errors (Feedback Loop)
        else Validation Passes
            Engine->>Runner: Execute Candidate on Evaluation Dataset
            loop For each query in Dataset
                Runner->>RAG: Invoke Pipeline with Settings Override
                RAG-->>Runner: Return Answer, Telemetry, Latency, Grading
            end
            Runner-->>Engine: Raw Results per Query
            Engine->>Stats: Compute Metrics, 95% CIs, Wilcoxon vs. Baseline
            Stats-->>Engine: Statistical Analysis
            Engine->>Store: Save Trial Result & Update Checkpoint
            Engine->>Sci: Provide Run Evidence & Performance Feedback
        end
    end
    Engine->>Store: Finalize Campaign
    Engine->>CLI: Export Leaderboard & Markdown Report
    CLI-->>User: Display Recommended Optimal Configuration
```

## 2. Deterministic Isolation Mechanics
In standard multi-agent setups, configuration objects are prone to concurrency races or global side effects. AES enforces strict isolation:
1. **Immutable Base Configuration:** `backend.core.config.get_settings()` returns the production baseline and is never modified in place.
2. **Context-Local Overrides:** `Settings.with_overrides(**kwargs)` constructs a lightweight, copy-on-write `Settings` instance with modified fields.
3. **Container Rebuilding:** `ServiceContainer.build(settings_override)` instantiates isolated components (e.g. `HybridRetriever` with updated $\alpha$ and $k$) without polluting singletons or other active worker threads.
4. **Cache & Websocket Bypass:** When invoked within an experiment runner, requests pass `skip_cache=True` and `skip_websocket=True` to eliminate caching artifacts and unnecessary socket broadcasts.

## 3. Dataset Splitting & Quality Assurance
- **Dataset V1 (Golden Evaluation Set):** 20 curated test cases across factual, multi-hop, adversarial, and ambiguous question types with verified ground-truth contexts and reference answers.
- **Dataset V2 (Synthetic Candidate Pool):** LLM-generated document question-context-answer triples. Tagged with `status="candidate"` and filtered by automated validation heuristics before being flagged for human verification.
- **Data Versioning:** Every trial records the checksum and identifier of the exact dataset used (`dataset_v1@sha256`), guaranteeing reproducibility.
