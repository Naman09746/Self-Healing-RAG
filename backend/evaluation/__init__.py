"""Self-Healing RAG Evaluation Framework (Phase 5).

Provides:
- RAGAS-based offline evaluation with Faithfulness, Answer Relevancy,
  Context Precision metrics
- Benchmark dataset loading and manipulation (``RAGBenchmark``,
  ``BenchmarkSample``)
- ``EvaluationRunner`` — orchestrator that drives evaluation across a dataset
- ``EvaluationQueue`` — Redis-backed async job queue for eval runs
- Convenient CLI via ``scripts/run_eval.py``
- Heuristic fallback when no LLM API key is configured (deterministic
  scores)
"""

from __future__ import annotations

from backend.evaluation.runner import EvaluationRunner, BenchmarkSample
from backend.evaluation.benchmark import RAGBenchmark
from backend.evaluation.queue import (
    EvaluationQueue,
    EvalJob,
    JobStatus,
)

__all__ = [
    "EvaluationRunner",
    "BenchmarkSample",
    "RAGBenchmark",
    "EvaluationQueue",
    "EvalJob",
    "JobStatus",
]