"""Integration tests for the evaluation pipeline.

Tests the full flow: load dataset → build samples → run evaluator →
check results. These tests require the default eval_dataset.jsonl to
exist and use the heuristic fallback (no LLM API key needed).
"""

from __future__ import annotations

import pytest

from backend.evaluation.runner import (
    EvaluationRunner,
    load_dataset,
    DEFAULT_DATASET_PATH,
)
from backend.evaluation.benchmark import RAGBenchmark


# ---------------------------------------------------------------------------
# Integration: Dataset → Runner → Results
# ---------------------------------------------------------------------------

class TestEvaluationPipeline:
    """Full integration of dataset loading and evaluation runner."""

    def test_dataset_exists_and_loadable(self) -> None:
        """The default benchmark dataset must exist and load correctly."""
        assert DEFAULT_DATASET_PATH.exists(), (
            f"Default dataset not found at {DEFAULT_DATASET_PATH}. "
            "Run `python scripts/generate_test_docs.py` first if needed."
        )
        samples = load_dataset()
        assert len(samples) > 0, "Dataset is empty"

        # Verify every sample has required fields
        for i, s in enumerate(samples):
            assert s.query, f"Sample {i}: missing query"
            assert s.expected_answer, f"Sample {i}: missing expected_answer"
            assert s.contexts, f"Sample {i}: missing contexts"

    def test_benchmark_round_trip(self) -> None:
        """Load → save → reload should preserve sample count."""
        benchmark = RAGBenchmark.load(DEFAULT_DATASET_PATH)
        original_count = len(benchmark)

        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w", encoding="utf-8")
        tmp_path = tmp.name
        tmp.close()

        try:
            benchmark.save(tmp_path)
            reloaded = RAGBenchmark.load(tmp_path)
            assert len(reloaded) == original_count
        finally:
            import os
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_runner_with_default_dataset(self) -> None:
        """Run the evaluator over the default dataset (limit=2 for speed)."""
        runner = EvaluationRunner(dataset_path=DEFAULT_DATASET_PATH)
        report = await runner.run(limit=2)

        assert report.num_queries == 2
        assert report.run_id.startswith("eval_")
        assert report.scores.error is None

        # Heuristic metrics must be in [0, 1]
        assert 0.0 <= report.scores.faithfulness <= 1.0
        assert 0.0 <= report.scores.answer_relevancy <= 1.0
        assert 0.0 <= report.scores.context_precision <= 1.0

        # Per-sample scores should be computed
        assert len(report.per_sample_scores) == 2
        for ps in report.per_sample_scores:
            assert "query" in ps
            assert "faithfulness" in ps
            assert "answer_relevancy" in ps
            assert "context_precision" in ps

    def test_runner_sync(self) -> None:
        """Synchronous wrapper should work the same as async."""
        runner = EvaluationRunner(dataset_path=DEFAULT_DATASET_PATH)
        report = runner.run_sync(limit=2)
        assert report.num_queries == 2
        assert report.scores.error is None

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_runner_with_bad_path_raises(self) -> None:
        runner = EvaluationRunner(dataset_path="/nonexistent/path.jsonl")
        with pytest.raises(FileNotFoundError):
            await runner.run()

    @pytest.mark.asyncio
    async def test_runner_handles_non_utf8(self) -> None:
        """Runner should handle datasets gracefully; non-UTF8 will fail on load."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="wb")
        tmp.write(b"\x80\x81\x82\n")  # invalid UTF-8
        tmp.close()

        tmp_path = tmp.name
        try:
            runner = EvaluationRunner(dataset_path=tmp_path)
            with pytest.raises(Exception):
                await runner.run()
        finally:
            import os
            os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Report output
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_report_contains_expected_fields(self) -> None:
        runner = EvaluationRunner(dataset_path=DEFAULT_DATASET_PATH)
        report = await runner.run(limit=1)

        report_dict = report.to_dict()
        assert "run_id" in report_dict
        assert "timestamp" in report_dict
        assert "num_queries" in report_dict
        assert "scores" in report_dict
        assert "per_sample_scores" in report_dict

        scores = report_dict["scores"]
        assert "faithfulness" in scores
        assert "answer_relevancy" in scores
        assert "context_precision" in scores