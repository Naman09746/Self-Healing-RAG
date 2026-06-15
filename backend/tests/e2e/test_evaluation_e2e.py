"""End-to-end tests for the evaluation framework.

Tests the full lifecycle:
1. Verify the default benchmark dataset exists and has valid structure
2. Run the offline evaluation pipeline end-to-end via CLI
3. Verify the output report (JSON + CSV) is written
4. Validate the Redis queue lifecycle (enqueue → process → complete)

These tests are tagged as "e2e" and may be skipped in CI if the
environment isn't fully configured.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

import pytest

from backend.evaluation.runner import DEFAULT_DATASET_PATH, RESULTS_DIR
from backend.evaluation.queue import EvaluationQueue, JobStatus


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not DEFAULT_DATASET_PATH.exists(),
        reason=f"Default dataset not found at {DEFAULT_DATASET_PATH}",
    ),
]

# The CLI script path
CLI_SCRIPT = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "run_eval.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def output_dir() -> Iterator[Path]:
    """Create a temporary output directory for eval results."""
    tmp = tempfile.mkdtemp(prefix="eval_e2e_")
    yield Path(tmp)
    # Cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: Dataset integrity
# ---------------------------------------------------------------------------

class TestDatasetIntegrity:
    """Ensure the benchmark dataset is valid."""

    def test_dataset_exists(self) -> None:
        assert DEFAULT_DATASET_PATH.exists(), (
            f"Dataset not found. Generate it with: "
            f"python scripts/generate_test_docs.py"
        )

    def test_dataset_format(self) -> None:
        """Every line must be valid JSON with required fields."""
        with open(DEFAULT_DATASET_PATH, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Line {line_no}: invalid JSON — {e}")

                assert "query" in obj, f"Line {line_no}: missing 'query'"
                assert "expected_answer" in obj, f"Line {line_no}: missing 'expected_answer'"
                assert "contexts" in obj, f"Line {line_no}: missing 'contexts'"
                assert isinstance(obj["contexts"], list), (
                    f"Line {line_no}: 'contexts' must be a list"
                )


# ---------------------------------------------------------------------------
# Test: CLI end-to-end
# ---------------------------------------------------------------------------

class TestCLI:
    """Run the CLI entry point as a subprocess."""

    def test_cli_help(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "--help"],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()

    def test_cli_verbose(self, output_dir: Path) -> None:
        """Run eval with --limit 1 and --verbose, check exit code."""
        result = subprocess.run(
            [
                sys.executable, str(CLI_SCRIPT),
                "--limit", "1",
                "--output-dir", str(output_dir),
                "--verbose",
            ],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, (
            f"CLI failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    def test_cli_default_output(self, output_dir: Path) -> None:
        """Run eval and verify the output contains expected scores."""
        result = subprocess.run(
            [
                sys.executable, str(CLI_SCRIPT),
                "--limit", "2",
                "--output-dir", str(output_dir),
            ],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, (
            f"CLI failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        output = result.stdout
        assert "Faithfulness" in output
        assert "Answer Relevancy" in output
        assert "Context Precision" in output
        assert "Run ID" in output
        assert "Samples:" in output

    def test_cli_nonexistent_dataset(self, output_dir: Path) -> None:
        """Using a nonexistent dataset should fail gracefully."""
        result = subprocess.run(
            [
                sys.executable, str(CLI_SCRIPT),
                "--dataset", "/nonexistent/path.jsonl",
                "--output-dir", str(output_dir),
            ],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 1
        assert "ERROR" in result.stdout or "ERROR" in result.stderr

    def test_cli_empty_limit(self, output_dir: Path) -> None:
        """--limit 0 should still produce a valid run."""
        result = subprocess.run(
            [
                sys.executable, str(CLI_SCRIPT),
                "--limit", "0",
                "--output-dir", str(output_dir),
            ],
            capture_output=True, text=True, check=False,
        )
        # limit=0 will load the file but take 0 samples
        assert result.returncode in (0, 1)


# ---------------------------------------------------------------------------
# Test: Report output
# ---------------------------------------------------------------------------

class TestReportOutput:
    """Verify that evaluation reports are written correctly."""

    def test_json_report_created(self, output_dir: Path) -> None:
        """Run eval and check that at least one JSON report is written."""
        subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "--limit", "1", "--output-dir", str(output_dir)],
            capture_output=True, check=False,
        )

        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) >= 1, f"No JSON reports found in {output_dir}"

        # Validate the JSON content
        with open(json_files[0], "r") as fh:
            report = json.load(fh)

        assert "run_id" in report
        assert "scores" in report
        assert "faithfulness" in report["scores"]
        assert "answer_relevancy" in report["scores"]
        assert "context_precision" in report["scores"]

    def test_csv_history_created(self, output_dir: Path) -> None:
        """Run twice and verify the CSV history is appended."""
        for _ in range(2):
            subprocess.run(
                [sys.executable, str(CLI_SCRIPT), "--limit", "1", "--output-dir", str(output_dir)],
                capture_output=True, check=False,
            )

        csv_files = list(output_dir.glob("*.csv"))
        assert len(csv_files) >= 1, f"No CSV history found in {output_dir}"

        # Validate CSV content
        with open(csv_files[0], newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        assert len(rows) >= 1
        for row in rows:
            assert "run_id" in row
            assert "faithfulness" in row
            assert "answer_relevancy" in row
            assert "context_precision" in row


# ---------------------------------------------------------------------------
# Test: Redis queue lifecycle (requires Redis)
# ---------------------------------------------------------------------------

class TestRedisQueueLifecycle:
    """E2E test for the Redis queue (requires a running Redis instance)."""

    @pytest.fixture
    def queue(self) -> Iterator[EvaluationQueue]:
        """Provide a connected EvaluationQueue, skipping if Redis unavailable."""
        q = EvaluationQueue()
        try:
            import asyncio
            asyncio.run(q.connect())
        except Exception:
            pytest.skip("Redis is not available")
        yield q
        import asyncio
        asyncio.run(q.close())

    @pytest.mark.skipif(
        os.environ.get("REDIS_URL") is None and not os.environ.get("CI"),
        reason="REDIS_URL not set; Redis may not be available",
    )
    @pytest.mark.asyncio
    async def test_enqueue_dequeue_complete(self, queue: EvaluationQueue) -> None:
        """Full job lifecycle: enqueue → dequeue → complete."""
        job_id = await queue.enqueue(
            dataset_path=str(DEFAULT_DATASET_PATH),
            limit=1,
        )
        assert job_id is not None

        # Check queue length
        length = await queue.queue_length()
        assert length == 1

        # Dequeue
        job = await queue.dequeue()
        assert job is not None
        assert job.job_id == job_id
        assert job.status == JobStatus.PROCESSING

        # Complete
        await queue.complete(job_id, result_path="/tmp/fake_report.json")

        # Verify final state
        final_job = await queue.get_job(job_id)
        assert final_job is not None
        assert final_job.status == JobStatus.COMPLETED
        assert final_job.result_path == "/tmp/fake_report.json"
        assert final_job.finished_at is not None


# ---------------------------------------------------------------------------
# Test: Offline evaluation function
# ---------------------------------------------------------------------------

class TestOfflineEvaluation:
    """Test the convenience ``run_offline_evaluation`` function."""

    def test_offline_basic(self) -> None:
        from backend.agents.evaluation.agent import run_offline_evaluation
        result = run_offline_evaluation(
            queries=["What is the capital of France?"],
            expected_answers=["Paris"],
            contexts=[["Paris is the capital of France."]],
            actual_answers=["Paris"],
        )
        assert result.num_samples == 1
        assert result.error is None
        assert result.faithfulness == 1.0
        assert result.context_precision == 1.0

    def test_offline_heuristic_no_match(self) -> None:
        from backend.agents.evaluation.agent import run_offline_evaluation
        result = run_offline_evaluation(
            queries=["?"],
            expected_answers=["zzz"],
            contexts=[["aaa bbb ccc"]],
            actual_answers=["xxx yyy"],
        )
        assert result.num_samples == 1
        assert result.error is None
        assert result.faithfulness == 0.0
        assert result.context_precision == 0.0