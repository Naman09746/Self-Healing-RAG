"""Unit tests for EvaluationRunner and BenchmarkSample."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from backend.evaluation.runner import (
    EvaluationRunner,
    BenchmarkSample,
    load_dataset,
    RAGPipelineAdapter,
    DEFAULT_DATASET_PATH,
)
from backend.evaluation.benchmark import RAGBenchmark


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dataset() -> Path:
    """Create a minimal JSONL dataset in a temp dir."""
    samples = [
        {"query": "Q1", "expected_answer": "A1", "contexts": ["C1"]},
        {"query": "Q2", "expected_answer": "A2", "contexts": ["C2"]},
    ]
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for s in samples:
        tmp.write(json.dumps(s) + "\n")
    tmp.close()
    path = Path(tmp.name)
    yield path
    path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# BenchmarkSample
# ---------------------------------------------------------------------------

class TestBenchmarkSample:
    def test_from_dict_full(self) -> None:
        d = {"query": "q", "expected_answer": "a", "contexts": ["c1", "c2"]}
        bs = BenchmarkSample.from_dict(d)
        assert bs.query == "q"
        assert bs.expected_answer == "a"
        assert bs.contexts == ["c1", "c2"]

    def test_from_dict_missing_fields(self) -> None:
        d = {}
        bs = BenchmarkSample.from_dict(d)
        assert bs.query == ""
        assert bs.expected_answer == ""
        assert bs.contexts == []

    def test_to_dict(self) -> None:
        bs = BenchmarkSample(query="q", expected_answer="a", contexts=["c"])
        d = bs.to_dict()
        assert d["query"] == "q"
        assert d["expected_answer"] == "a"
        assert d["contexts"] == ["c"]


# ---------------------------------------------------------------------------
# load_dataset
# ---------------------------------------------------------------------------

class TestLoadDataset:
    def test_loads_from_default_path(self) -> None:
        """The default dataset should exist and have at least one sample."""
        assert DEFAULT_DATASET_PATH.exists(), (
            f"Default dataset not found at {DEFAULT_DATASET_PATH}"
        )
        samples = load_dataset()
        assert len(samples) > 0

    def test_loads_from_custom_path(self, temp_dataset: Path) -> None:
        samples = load_dataset(temp_dataset)
        assert len(samples) == 2

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_dataset(Path("/nonexistent/path.jsonl"))


# ---------------------------------------------------------------------------
# RAGPipelineAdapter
# ---------------------------------------------------------------------------

class TestRAGPipelineAdapter:
    @pytest.mark.asyncio
    async def test_placeholder_answer(self) -> None:
        adapter = RAGPipelineAdapter()
        answer, used = await adapter.answer("test query", ["ctx1"])
        assert "test query" in answer
        assert used == ["ctx1"]


# ---------------------------------------------------------------------------
# EvaluationRunner
# ---------------------------------------------------------------------------

class TestEvaluationRunner:
    @pytest.mark.asyncio
    async def test_run_with_empty_dataset(self) -> None:
        """When the dataset has zero samples, the runner returns an error report."""
        # Create an empty file
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        tmp.close()
        empty_path = Path(tmp.name)
        try:
            runner = EvaluationRunner(dataset_path=empty_path)
            report = await runner.run()
            assert report.num_queries == 0
            assert report.scores.error is not None
        finally:
            empty_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_run_with_limit(self, temp_dataset: Path) -> None:
        runner = EvaluationRunner(dataset_path=temp_dataset)
        report = await runner.run(limit=1)
        assert report.num_queries == 1

    @pytest.mark.asyncio
    async def test_run_full(self, temp_dataset: Path) -> None:
        runner = EvaluationRunner(dataset_path=temp_dataset)
        report = await runner.run()

        assert report.num_queries == 2
        assert report.run_id.startswith("eval_")
        assert report.scores.error is None

        # Scores should be computed (heuristic)
        assert report.scores.faithfulness >= 0.0
        assert report.scores.answer_relevancy >= 0.0
        assert report.scores.context_precision >= 0.0

        # Per-sample scores
        assert len(report.per_sample_scores) == 2

    def test_run_sync(self, temp_dataset: Path) -> None:
        runner = EvaluationRunner(dataset_path=temp_dataset)
        report = runner.run_sync(limit=1)
        assert report.num_queries == 1


# ---------------------------------------------------------------------------
# RAGBenchmark
# ---------------------------------------------------------------------------

class TestRAGBenchmark:
    def test_load_and_save(self, temp_dataset: Path) -> None:
        benchmark = RAGBenchmark.load(temp_dataset)
        assert len(benchmark) == 2

        # Round-trip
        save_path = temp_dataset.with_suffix(".saved.jsonl")
        try:
            benchmark.save(save_path)
            reloaded = RAGBenchmark.load(save_path)
            assert len(reloaded) == 2
            assert reloaded[0].query == "Q1"
        finally:
            save_path.unlink(missing_ok=True)

    def test_slice(self) -> None:
        samples = [
            BenchmarkSample(query=str(i), expected_answer="a", contexts=["c"])
            for i in range(5)
        ]
        bm = RAGBenchmark(samples)
        sliced = bm.slice(1, 4)
        assert len(sliced) == 3
        assert sliced[0].query == "1"

    def test_shuffle(self) -> None:
        samples = [
            BenchmarkSample(query=str(i), expected_answer="a", contexts=["c"])
            for i in range(10)
        ]
        bm = RAGBenchmark(samples)
        shuffled = bm.shuffle(seed=42)
        # Should have same elements but likely different order
        assert len(shuffled) == 10
        queries = [s.query for s in shuffled]
        assert sorted(queries) == [str(i) for i in range(10)]