# ADR-003: Dual-Dataset Strategy (Golden Regression vs. Synthetic Candidates)

## Status
Accepted

## Context
RAG evaluation requires high-quality ground-truth benchmarks. Using purely synthetic LLM-generated Q&A triples risks data contamination, hallucinations in ground truth, and optimistic evaluation bias. Conversely, relying solely on a small static dataset risks overfitting hyper-parameters to narrow linguistic patterns.

## Decision
We establish a dual-dataset regime:
1. **Dataset V1 (Golden Evaluation Set):** 20 human-verified, curated queries spanning factual, multi-hop, adversarial, and ambiguous cases. Serves as the mandatory anchor for all regression checks and paired Wilcoxon statistical tests.
2. **Dataset V2 (Synthetic Candidate Set):** LLM-generated document questions stored separately with an explicit `status: "candidate"` and `human_reviewed: false` flag.

Dataset V2 samples can only be included in trial evaluations when explicitly commanded by the operator via the `--include-candidates` flag.

## Consequences
- **Positive:** Guarantees that regression benchmarks are never polluted by untested synthetic questions while still providing a clear path for expanding evaluation corpora.
- **Negative:** Maintaining ground truth requires human review effort when promoting candidate samples.
