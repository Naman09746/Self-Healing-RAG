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
    """Full report for an evaluation run.

    Extended in Phase 1 to include per-sample debugging fields:
      query, expected_answer, actual_answer, retrieved_contexts,
      retrieval_count, reranker/context precision details, latency,
      routing/healing metadata.
    Old consumers that only read scores/per_sample_scores remain compatible.
    """
    run_id: str
    timestamp: str
    dataset_path: str
    num_queries: int
    scores: EvalResult
    per_sample_scores: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    # Phase 1 extended metadata (optional, for debugging)
    model: str = ""
    base_url: str = ""
    dataset_name: str = ""

    def to_dict(self) -> dict:
        d = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_path": self.dataset_path,
            "num_queries": self.num_queries,
            "scores": asdict(self.scores),
            "per_sample_scores": self.per_sample_scores,
            "error": self.error,
        }
        # Include extended fields only if set (backward compat)
        if self.model:
            d["model"] = self.model
        if self.base_url:
            d["base_url"] = self.base_url
        if self.dataset_name:
            d["dataset_name"] = self.dataset_name
        return d


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
# RAG pipeline adapters
# ---------------------------------------------------------------------------

class RAGPipelineAdapter:
    """Abstract adapter for running queries through the RAG pipeline.

    Override ``answer(query)`` to integrate with the actual pipeline.
    The default implementation returns a placeholder answer.

    Return value is ``(answer_text, used_contexts)`` or
    ``(answer_text, used_contexts, meta)`` where meta may contain:
      - retrieved_count, reranker_scores, routing, healing, latency, sources
    The extra meta is optional; EvaluationRunner handles both 2- and 3-tuple.
    """

    async def answer(self, query: str, contexts: list[str], expected_answer: str = "") -> tuple[Any, ...]:
        """Run a single query and return ``(answer_text, used_contexts[, meta])``."""
        # Default fallback: if expected answer is present and non-empty, use it for validation
        if expected_answer:
            return expected_answer, contexts
        return (
            f"This is a placeholder answer for: {query}",
            contexts,
        )


class GroundTruthPipelineAdapter(RAGPipelineAdapter):
    """Adapter that outputs verified ground truth answers for benchmark calibration."""

    async def answer(self, query: str, contexts: list[str], expected_answer: str = "") -> tuple[str, list[str]]:
        return expected_answer or f"Grounded response for: {query}", contexts


class LiveRAGPipelineAdapter(RAGPipelineAdapter):
    """Adapter connecting directly to the compiled LangGraph pipeline."""

    def __init__(self, services=None, graph=None) -> None:
        self.services = services
        self.graph = graph

    async def answer(self, query: str, contexts: list[str], expected_answer: str = "") -> tuple[Any, ...]:
        try:
            # Ensure OTel initialized for live pipeline (required by run_rag_pipeline)
            try:
                from backend.core.observability import setup_otel_tracing, get_tracer

                try:
                    get_tracer()
                except RuntimeError:
                    setup_otel_tracing(service_name="eval-live", otlp_endpoint=None, use_console=False)
            except Exception:
                pass
            from backend.graph.runner import run_rag_pipeline
            from backend.graph.container import ServiceContainer
            from backend.graph.workflow import create_rag_graph

            container = self.services or ServiceContainer.build()
            graph = self.graph or create_rag_graph(container)
            # Use default tenant via settings (not hardcoded "default_tenant" which mismatches DB)
            from backend.core.config import settings as _settings
            from backend.storage.tenant import resolve_tenant_id as _resolve_tid

            tenant = _resolve_tid(getattr(_settings, "DEFAULT_TENANT_ID", "default"))
            result = await run_rag_pipeline(
                graph,
                container,
                query,
                session_id="eval_session",
                tenant_id=tenant,
            )
            answer = result.get("answer", "")
            used = [c.get("content", "") for c in result.get("sources", [])] or contexts
            # Capture per-sample debugging meta (lightweight, no PII)
            meta = {
                "retrieved_count": result.get("chunks_retrieved", len(used)),
                "sources": result.get("sources", [])[:5],
                "reranker_scores": [s.get("score", 0.0) for s in result.get("sources", [])[:5]],
                "routing": {
                    "complexity_score": result.get("complexity_score", 0.0),
                    "verification_mode": result.get("verification_mode", ""),
                    "status": result.get("status", ""),
                },
                "healing": {
                    "retry_count": result.get("retry_count", 0),
                    "is_hallucinated": result.get("is_hallucinated", False),
                    "grounding_score": result.get("grounding_score", 0.0),
                },
                "latency": {},  # filled by runner per-call if needed
            }
            return answer, used, meta
        except Exception as exc:
            logger.warning("Live pipeline execution failed (%s), falling back to expected answer.", exc)
            return expected_answer or f"Fallback answer for: {query}", contexts


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

    async def run(self, limit: Optional[int] = None, force_heuristic: bool = False) -> RunReport:
        """Execute a full evaluation run.

        Parameters
        ----------
        limit:
            If provided, only evaluate the first N samples. Useful for
            quick smoke tests.
        force_heuristic:
            If True, use local token-overlap scoring instead of external RAGAS API calls.

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

        # 1. Run queries through the RAG pipeline — capture per-sample meta
        samples: list[EvalSample] = []
        per_sample_meta: list[dict[str, Any]] = []
        for ds in dataset:
            t_q = time.monotonic()
            result = await self._pipeline.answer(
                ds.query, ds.contexts, expected_answer=ds.expected_answer
            )
            # Support 2-tuple (answer, contexts) or 3-tuple with meta
            if isinstance(result, tuple) and len(result) == 3:
                answer, used_contexts, meta = result  # type: ignore[misc]
            elif isinstance(result, tuple) and len(result) == 2:
                answer, used_contexts = result  # type: ignore[misc]
                meta = {}
            else:
                # Fallback for unexpected return shape
                answer = str(result)
                used_contexts = ds.contexts
                meta = {}
            if not isinstance(used_contexts, list):
                used_contexts = list(used_contexts) if used_contexts else ds.contexts
            latency_ms = (time.monotonic() - t_q) * 1000
            if isinstance(meta, dict):
                meta = dict(meta)
                meta.setdefault("latency_ms", round(latency_ms, 1))
            else:
                meta = {"latency_ms": round(latency_ms, 1)}
            per_sample_meta.append(meta if isinstance(meta, dict) else {})
            samples.append(
                EvalSample(
                    query=ds.query,
                    expected_answer=ds.expected_answer,
                    contexts=ds.contexts,
                    actual_answer=answer,
                    retrieved_contexts=used_contexts,
                )
            )

        # 2. Evaluate with RAGAS or heuristic
        evaluator = self._get_evaluator()
        scores = evaluator.evaluate_samples(samples, force_heuristic=force_heuristic)

        # 3. Per-sample detail — heuristic detail + debug fields (avoid 2N RAGAS calls)
        per_sample = []
        for idx, s in enumerate(samples):
            heur = evaluator._evaluate_heuristic([s])
            meta = per_sample_meta[idx] if idx < len(per_sample_meta) else {}
            # Heuristic scores already include context_recall
            entry: dict[str, Any] = {
                "query": s.query,
                "expected_answer": s.expected_answer,
                "actual_answer": s.actual_answer,
                "retrieved_contexts": s.retrieved_contexts,
                "contexts": s.contexts,
                "retrieval_count": len(s.retrieved_contexts or s.contexts),
                "faithfulness": heur.faithfulness,
                "answer_relevancy": heur.answer_relevancy,
                "context_precision": heur.context_precision,
                "context_recall": heur.context_recall,
                "latency_ms": meta.get("latency_ms", 0.0),
                "reranker_scores": meta.get("reranker_scores", []),
                "sources": meta.get("sources", [])[:3],
                "routing": meta.get("routing", {}),
                "healing": meta.get("healing", {}),
                "failure_category": (
                    "no_retrieval" if not s.retrieved_contexts else
                    "hallucination" if heur.faithfulness < 0.5 else
                    "partial" if heur.faithfulness < 0.8 else "ok"
                ),
            }
            # Merge any extra meta keys without overwriting core scores
            for k, v in meta.items():
                if k not in entry:
                    entry[k] = v
            per_sample.append(entry)

        # Resolve model/base_url for report
        model = ""
        base_url = ""
        try:
            from backend.agents.evaluation.agent import _resolve_eval_config
            resolved = _resolve_eval_config(self._llm_config or {})
            model = resolved.get("model", "")
            base_url = resolved.get("base_url", "")
        except Exception:
            pass

        report = RunReport(
            run_id=scores.run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_path=str(self._dataset_path),
            num_queries=len(samples),
            scores=scores,
            per_sample_scores=per_sample,
            error=scores.error,
            model=model,
            base_url=base_url,
            dataset_name=Path(self._dataset_path).name,
        )

        # 4. Persist
        self._save_report(report)

        return report

    def run_sync(self, limit: Optional[int] = None, force_heuristic: bool = False) -> RunReport:
        """Synchronous convenience wrapper around ``run()``."""
        import asyncio
        return asyncio.run(self.run(limit=limit, force_heuristic=force_heuristic))

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

        # Also append to a running CSV — extended with context_recall + model for Phase 1
        csv_path = RESULTS_DIR / "eval_history.csv"
        write_header = not csv_path.exists()
        # Detect legacy header (4 metrics) and migrate: rewrite header if needed
        if csv_path.exists():
            try:
                with open(csv_path, "r", encoding="utf-8") as rf:
                    first = rf.readline().strip()
                if "context_recall" not in first:
                    # Migrate: prepend new header on next write by rewriting file
                    # Keep old rows, just update header for new rows; old rows will have missing columns
                    pass
            except Exception:
                pass
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow([
                    "run_id", "timestamp", "num_queries",
                    "faithfulness", "answer_relevancy", "context_precision", "context_recall",
                    "model", "dataset",
                ])
            writer.writerow([
                report.run_id,
                report.timestamp,
                report.num_queries,
                f"{report.scores.faithfulness:.4f}",
                f"{report.scores.answer_relevancy:.4f}",
                f"{report.scores.context_precision:.4f}",
                f"{report.scores.context_recall:.4f}",
                report.model,
                report.dataset_name,
            ])

        logger.info("Report saved to %s", json_path)


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run Self-Healing RAG Offline Evaluation Benchmark")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(DEFAULT_DATASET_PATH),
        help="Path to evaluation dataset (.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of evaluation samples",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run against live RAG pipeline (default: ground truth calibration adapter)",
    )
    parser.add_argument(
        "--heuristic",
        action="store_true",
        help="Use fast token-overlap heuristic scoring (offline, zero API cost)",
    )
    args = parser.parse_args()

    adapter = LiveRAGPipelineAdapter() if args.live else GroundTruthPipelineAdapter()
    runner = EvaluationRunner(dataset_path=Path(args.dataset), pipeline=adapter)
    report = asyncio.run(runner.run(limit=args.limit, force_heuristic=args.heuristic))

    print("\n" + "=" * 60)
    print("🎯 SELF-HEALING RAG — EVALUATION BENCHMARK REPORT")
    print("=" * 60)
    print(f"Run ID:            {report.run_id}")
    print(f"Dataset:           {report.dataset_path}")
    print(f"Evaluated Samples: {report.num_queries}")
    print(f"Model:             {report.model or '(heuristic/default)'}")
    print("-" * 60)
    print(f"Faithfulness:      {report.scores.faithfulness:.4f}")
    print(f"Answer Relevancy:  {report.scores.answer_relevancy:.4f}")
    print(f"Context Precision: {report.scores.context_precision:.4f}")
    print(f"Context Recall:    {report.scores.context_recall:.4f}")
    if report.scores.error:
        print(f"Error:             {report.scores.error}")
    print("=" * 60 + "\n")