#!/usr/bin/env python3
"""CLI entry point for running RAG evaluation offline.

Usage::

    # Run the full benchmark
    python scripts/run_eval.py

    # Limit to first 5 samples for quick smoke test
    python scripts/run_eval.py --limit 5

    # Use a custom dataset
    python scripts/run_eval.py --dataset data/custom_benchmark.jsonl

    # Enqueue via Redis and return immediately
    python scripts/run_eval.py --queue

    # Use an LLM API key for RAGAS
    python scripts/run_eval.py --api-key sk-...

    # Output results to a specific directory
    python scripts/run_eval.py --output-dir ./my_eval_results
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.evaluation.runner import EvaluationRunner, DEFAULT_DATASET_PATH
from backend.evaluation.queue import EvaluationQueue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run offline RAG evaluation using RAGAS metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help=f"Path to JSONL dataset (default: {DEFAULT_DATASET_PATH})",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only evaluate the first N samples (default: all).",
    )

    parser.add_argument(
        "--queue",
        action="store_true",
        help="Enqueue the evaluation as a Redis-backed job instead of running inline.",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key for RAGAS LLM-based metrics.",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="eval_results",
        help="Directory to write results (default: eval_results).",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug-level logging.",
    )

    return parser


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

async def _run(
    dataset_path: Path,
    limit: Optional[int],
    queue_mode: bool,
    llm_config: Optional[dict],
    output_dir: str,
) -> int:
    """Execute the evaluation and return a process exit code."""

    import os

    # Override the results dir in the runner module
    from backend.evaluation import runner as runner_mod
    runner_mod.RESULTS_DIR = Path(output_dir)
    runner_mod.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if queue_mode:
        # ------------------------------------------------------------------
        # Redis-backed queue mode
        # ------------------------------------------------------------------
        logger.info("Enqueuing evaluation job to Redis queue …")
        eval_queue = EvaluationQueue()
        try:
            await eval_queue.connect()
            job_id = await eval_queue.enqueue(
                dataset_path=str(dataset_path),
                limit=limit,
            )
            print(f"Job enqueued: {job_id}")
            print(f"Check status with: redis-cli hgetall eval:job:{job_id}")
            return 0
        finally:
            await eval_queue.close()

    # ------------------------------------------------------------------
    # Inline / synchronous mode
    # ------------------------------------------------------------------
    runner = EvaluationRunner(
        dataset_path=dataset_path,
        llm_config=llm_config,
    )

    logger.info("Starting evaluation (dataset=%s, limit=%s) …", dataset_path, limit)
    report = await runner.run(limit=limit)

    scores = report.scores
    print("=" * 60)
    print(f"  Run ID:         {report.run_id}")
    print(f"  Samples:        {report.num_queries}")
    print(f"  Duration:       {scores.duration_seconds:.2f}s")
    print(f"  Error:          {scores.error or 'none'}")
    print("-" * 60)
    print(f"  Faithfulness:     {scores.faithfulness:.4f}")
    print(f"  Answer Relevancy: {scores.answer_relevancy:.4f}")
    print(f"  Context Precision:{scores.context_precision:.4f}")
    print("=" * 60)

    if scores.error:
        logger.error("Evaluation failed: %s", scores.error)
        return 1

    return 0


def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s | %(message)s",
        stream=sys.stderr,
    )

    dataset_path = Path(args.dataset) if args.dataset else DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}", file=sys.stderr)
        return 1

    llm_config: Optional[dict] = None
    if args.api_key:
        llm_config = {"api_key": args.api_key}

    return asyncio.run(
        _run(
            dataset_path=dataset_path,
            limit=args.limit,
            queue_mode=args.queue,
            llm_config=llm_config,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    sys.exit(main())