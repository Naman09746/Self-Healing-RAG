"""EvaluationRunner — orchestrates offline evaluation runs.

Loads a benchmark dataset, runs the RAG pipeline for each query (or
accepts pre-computed answers), then computes RAGAS metrics and persists
results.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional

from backend.agents.evaluation.agent import (
    RAGASEvaluator,
    EvalSample,
    EvalResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "eval_dataset.jsonl"
RESULTS_DIR = Path("eval_results")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkSample:
    """A single entry from the benchmark dataset."""
    query: str
    expected_answer: str
    contexts: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BenchmarkSample":
        return cls(
            query=str(d.get("query", "")),
            expected_answer=str(d.get("expected_answer", "")),
            contexts=list(d.get("contexts", [])),
        )


@dataclass
class RunReport:
    """Full report for an evaluation run."""
    run_id: str
    timestamp: str
    dataset_path: str
    num_queries: int
    scores: EvalResult
    per_sample_scores: list[dict] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_path": self.dataset_path,
            "num_queries": self.num_queries,
            "scores": asdict(self.scores),
            "per_sample_scores": self.per_sample_scores,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------

def load_dataset(path: Optional[Path | str] = None) -> list[BenchmarkSample]:
    """Load the benchmark dataset from a JSONL file.

    Each line is a JSON object with ``query``, ``expected_answer``, and
    ``contexts`` keys.
    """
    if path is None:
        path = DEFAULT_DATASET_PATH
    elif isinstance(path, str):
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at {path}")

    samples: list[BenchmarkSample] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            samples.append(BenchmarkSample.from_dict(d))

    logger.info("Loaded %d samples from %s", len(samples), path)
    return samples


# ---------------------------------------------------------------------------
# RAG pipeline adapter
# ---------------------------------------------------------------------------

class RAGPipelineAdapter:
    """Abstract adapter for running queries through the RAG pipeline.

    Override ``answer(query)`` to integrate with the actual pipeline.
    The default implementation returns a placeholder answer.
    """

    async def answer(self, query: str, contexts: list[str]) -> tuple[str, list[str]]:
        """Run a single query and return ``(answer_text, used_contexts)``.

        Override this in a subclass to connect to the real pipeline.
        """
        # Placeholder: in a real integration this would call the graph runner.
        return (
            f"This is a placeholder answer for: {query}",
            contexts,
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class EvaluationRunner:
    """Orchestrates a full evaluation run.

    Typical usage::

        runner = EvaluationRunner(dataset_path="...")
        report = await runner.run()
        print(report.scores)
    """

    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        llm_config: Optional[dict] = None,
        pipeline: Optional[RAGPipelineAdapter] = None,
    ) -> None:
        self._dataset_path = dataset_path or DEFAULT_DATASET_PATH
        self._llm_config = llm_config
        self._pipeline = pipeline or RAGPipelineAdapter()

        # Lazily initialised
        self._evaluator: Optional[RAGASEvaluator] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, limit: Optional[int] = None) -> RunReport:
        """Execute a full evaluation run.

        Parameters
        ----------
        limit:
            If provided, only evaluate the first N samples. Useful for
            quick smoke tests.

        Returns
        -------
        RunReport
        """
        from datetime import datetime, timezone

        dataset = load_dataset(self._dataset_path)
        if limit is not None:
            dataset = dataset[:limit]

        if not dataset:
            return RunReport(
                run_id=f"eval_{int(time.time())}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                dataset_path=str(self._dataset_path),
                num_queries=0,
                scores=EvalResult(error="Empty dataset"),
            )

        # 1. Run queries through the RAG pipeline
        samples: list[EvalSample] = []
        for ds in dataset:
            answer, used_contexts = await self._pipeline.answer(
                ds.query, ds.contexts
            )
            samples.append(
                EvalSample(
                    query=ds.query,
                    expected_answer=ds.expected_answer,
                    contexts=ds.contexts,
                    actual_answer=answer,
                    retrieved_contexts=used_contexts,
                )
            )

        # 2. Evaluate with RAGAS
        evaluator = self._get_evaluator()
        scores = evaluator.evaluate_samples(samples)

        # 3. Per-sample detail
        per_sample = []
        for s in samples:
            sample_eval = evaluator.evaluate_samples([s])
            per_sample.append(
                {
                    "query": s.query,
                    "faithfulness": sample_eval.faithfulness,
                    "answer_relevancy": sample_eval.answer_relevancy,
                    "context_precision": sample_eval.context_precision,
                }
            )

        report = RunReport(
            run_id=scores.run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_path=str(self._dataset_path),
            num_queries=len(samples),
            scores=scores,
            per_sample_scores=per_sample,
            error=scores.error,
        )

        # 4. Persist
        self._save_report(report)

        return report

    def run_sync(self, limit: Optional[int] = None) -> RunReport:
        """Synchronous convenience wrapper around ``run()``."""
        import asyncio
        return asyncio.run(self.run(limit=limit))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_evaluator(self) -> RAGASEvaluator:
        if self._evaluator is None:
            self._evaluator = RAGASEvaluator(llm_config=self._llm_config)
        return self._evaluator

    def _save_report(self, report: RunReport) -> None:
        """Write the report as JSON to ``eval_results/``."""
        RESULTS_DIR.mkdir(exist_ok=True)

        json_path = RESULTS_DIR / f"{report.run_id}.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2, default=str)

        # Also append to a running CSV
        csv_path = RESULTS_DIR / "eval_history.csv"
        write_header = not csv_path.exists()
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow([
                    "run_id", "timestamp", "num_queries",
                    "faithfulness", "answer_relevancy", "context_precision",
                ])
            writer.writerow([
                report.run_id,
                report.timestamp,
                report.num_queries,
                f"{report.scores.faithfulness:.4f}",
                f"{report.scores.answer_relevancy:.4f}",
                f"{report.scores.context_precision:.4f}",
            ])

        logger.info("Report saved to %s", json_path)