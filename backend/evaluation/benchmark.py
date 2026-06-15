"""RAGBenchmark — benchmark dataset loader and runner.

Provides ``RAGBenchmark`` for loading and managing evaluation datasets
and the ``BenchmarkSuite`` for running multiple test scenarios.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benchmark sample
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkSample:
    """A single (query, ground_truth) pair from a benchmark dataset."""
    query: str
    expected_answer: str
    contexts: list[str]  # Gold-standard contexts

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BenchmarkSample":
        return cls(
            query=str(d.get("query", "")),
            expected_answer=str(d.get("expected_answer", "")),
            contexts=list(d.get("contexts", [])),
        )


# ---------------------------------------------------------------------------
# Benchmark dataset
# ---------------------------------------------------------------------------

class RAGBenchmark:
    """Represents an evaluation dataset.

    Datasets are stored as JSONL files with one JSON object per line::

        {"query": "...", "expected_answer": "...", "contexts": ["..."]}

    Usage::

        dataset = RAGBenchmark.load("data/benchmark.jsonl")
        for sample in dataset:
            print(sample.query)
    """

    def __init__(self, samples: list[BenchmarkSample] | None = None) -> None:
        self._samples = samples or []

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str) -> "RAGBenchmark":
        """Load samples from a JSONL file."""
        path = Path(path)
        samples: list[BenchmarkSample] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    samples.append(BenchmarkSample.from_dict(json.loads(line)))
        logger.info("Loaded benchmark with %d samples from %s", len(samples), path)
        return cls(samples)

    def save(self, path: Path | str) -> None:
        """Persist samples as JSONL."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for sample in self._samples:
                fh.write(json.dumps(sample.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Saved benchmark (%d samples) to %s", len(self._samples), path)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> BenchmarkSample:
        return self._samples[idx]

    def __iter__(self):
        return iter(self._samples)

    @property
    def samples(self) -> list[BenchmarkSample]:
        return list(self._samples)

    def slice(self, start: int = 0, end: Optional[int] = None) -> "RAGBenchmark":
        """Return a sub-benchmark (sliced view)."""
        return RAGBenchmark(self._samples[start:end])

    def shuffle(self, seed: int = 42) -> "RAGBenchmark":
        """Return a shuffled copy."""
        import random
        rng = random.Random(seed)
        shuffled = list(self._samples)
        rng.shuffle(shuffled)
        return RAGBenchmark(shuffled)


# ---------------------------------------------------------------------------
# Benchmark suite (multiple scenarios)
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkSuite:
    """A collection of named benchmarks for multi-scenario evaluation.

    Example::

        suite = BenchmarkSuite()
        suite.add("single_hop", single_hop_dataset)
        suite.add("multi_hop",  multi_hop_dataset)
        suite.run_all(...)
    """

    benchmarks: dict[str, RAGBenchmark] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.benchmarks is None:
            self.benchmarks = {}

    def add(self, name: str, benchmark: RAGBenchmark) -> None:
        """Register a named benchmark."""
        self.benchmarks[name] = benchmark

    @property
    def names(self) -> list[str]:
        return list(self.benchmarks.keys())

    def total_samples(self) -> int:
        return sum(len(b) for b in self.benchmarks.values())

    def get(self, name: str) -> Optional[RAGBenchmark]:
        return self.benchmarks.get(name)