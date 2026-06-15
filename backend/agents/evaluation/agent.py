"""Evaluation Agent — Offline RAGAS-based evaluation of pipeline outputs.

Uses RAGAS metrics to compute:
    - Faithfulness
    - Answer Relevancy
    - Context Precision

Call ``run_offline_evaluation()`` after the pipeline has produced results
for a batch of queries. Results are returned as a dict of metric scores.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvalSample:
    """A single evaluation sample."""
    query: str
    expected_answer: str
    contexts: list[str]
    actual_answer: str = ""
    retrieved_contexts: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating one or more samples."""
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    run_id: str = ""
    num_samples: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# RAGAS evaluator (with graceful fallback)
# ---------------------------------------------------------------------------

class RAGASEvaluator:
    """Thin wrapper around RAGAS metrics.

    Falls back to heuristic / dummy scores when RAGAS is not available
    (e.g. no LLM endpoint configured, missing API key).
    """

    def __init__(self, llm_config: Optional[dict] = None) -> None:
        self._llm_config = llm_config or {}
        self._ragas_available = False

        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
            )

            # If an explicit API key was provided, set it
            if self._llm_config.get("api_key"):
                import os
                os.environ["OPENAI_API_KEY"] = self._llm_config["api_key"]

            # Quick smoke-test: try importing datasets (needed by RAGAS)
            import datasets  # noqa: F401

            self._evaluate = evaluate
            self._faithfulness = faithfulness
            self._answer_relevancy = answer_relevancy
            self._context_precision = context_precision
            self._ragas_available = True
            logger.info("RAGAS evaluation backend is available.")

        except ImportError as exc:
            logger.warning(
                "RAGAS or datasets not installed (%s). "
                "Falling back to heuristic scoring.",
                exc,
            )
        except Exception as exc:
            logger.warning(
                "RAGAS initialisation failed (%s). "
                "Falling back to heuristic scoring.",
                exc,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_samples(self, samples: list[EvalSample]) -> EvalResult:
        """Evaluate a list of ``EvalSample`` objects.

        Returns an ``EvalResult`` with mean scores across all samples.
        """
        if not samples:
            return EvalResult(error="No samples provided.")

        t0 = time.monotonic()
        run_id = f"eval_{int(t0)}"

        if self._ragas_available:
            result = self._evaluate_with_ragas(samples)
        else:
            result = self._evaluate_heuristic(samples)

        result.run_id = run_id
        result.num_samples = len(samples)
        result.duration_seconds = time.monotonic() - t0

        logger.info(
            "Evaluation %s complete: "
            "faithfulness=%.3f, answer_relevancy=%.3f, context_precision=%.3f "
            "(%d samples in %.2f s)",
            run_id,
            result.faithfulness,
            result.answer_relevancy,
            result.context_precision,
            result.num_samples,
            result.duration_seconds,
        )

        return result

    # ------------------------------------------------------------------
    # RAGAS path
    # ------------------------------------------------------------------

    def _evaluate_with_ragas(self, samples: list[EvalSample]) -> EvalResult:
        """Evaluate using the real RAGAS library."""
        try:
            from datasets import Dataset

            data = {
                "question": [s.query for s in samples],
                "answer": [s.actual_answer for s in samples],
                "contexts": [s.retrieved_contexts or s.contexts for s in samples],
                "ground_truth": [s.expected_answer for s in samples],
            }

            dataset = Dataset.from_dict(data)

            scores = self._evaluate(
                dataset,
                metrics=[
                    self._faithfulness,
                    self._answer_relevancy,
                    self._context_precision,
                ],
            )

            return EvalResult(
                faithfulness=float(scores.get("faithfulness", 0.0)),
                answer_relevancy=float(scores.get("answer_relevancy", 0.0)),
                context_precision=float(scores.get("context_precision", 0.0)),
            )

        except Exception as exc:
            logger.exception("RAGAS evaluation failed.")
            return EvalResult(error=str(exc))

    # ------------------------------------------------------------------
    # Heuristic fallback path
    # ------------------------------------------------------------------

    def _evaluate_heuristic(self, samples: list[EvalSample]) -> EvalResult:
        """Compute heuristic scores when RAGAS is not available.

        Faithfulness: fraction of overlapping tokens between answer and contexts.
        Answer Relevancy: fraction of question tokens found in the answer.
        Context Precision: fraction of context sentences that contain
        key terms from the expected answer.
        """
        total_faith = total_rel = total_prec = 0.0

        for sample in samples:
            # Faithfulness
            answer_tokens = set(sample.actual_answer.lower().split())
            context_text = " ".join(sample.retrieved_contexts or sample.contexts)
            if answer_tokens:
                overlap = sum(
                    1 for t in answer_tokens if t in context_text.lower()
                )
                total_faith += overlap / len(answer_tokens)
            else:
                total_faith += 0.0

            # Answer Relevancy
            question_tokens = set(sample.query.lower().split())
            answer_text = sample.actual_answer.lower()
            if question_tokens:
                q_overlap = sum(
                    1 for t in question_tokens if t in answer_text
                )
                total_rel += q_overlap / len(question_tokens)
            else:
                total_rel += 0.0

            # Context Precision
            expected_tokens = set(sample.expected_answer.lower().split())
            context_text_lower = context_text.lower()
            if expected_tokens and context_text_lower:
                e_overlap = sum(
                    1 for t in expected_tokens if t in context_text_lower
                )
                total_prec += e_overlap / len(expected_tokens)
            else:
                total_prec += 0.0

        n = len(samples)
        return EvalResult(
            faithfulness=total_faith / n,
            answer_relevancy=total_rel / n,
            context_precision=total_prec / n,
        )


# ---------------------------------------------------------------------------
# Convenience: one-shot offline evaluation
# ---------------------------------------------------------------------------

def run_offline_evaluation(
    queries: list[str],
    expected_answers: list[str],
    contexts: list[list[str]],
    actual_answers: list[str],
    retrieved_contexts: Optional[list[list[str]]] = None,
    llm_config: Optional[dict] = None,
) -> EvalResult:
    """Run offline RAGAS evaluation on pipeline outputs.

    Parameters
    ----------
    queries:
        The input queries for each sample.
    expected_answers:
        Ground-truth / reference answers.
    contexts:
        The relevant context passages for each query.
    actual_answers:
        The answers produced by the RAG pipeline.
    retrieved_contexts:
        The contexts actually retrieved by the pipeline (if different
        from the gold ``contexts``). Useful for measuring retrieval quality.
    llm_config:
        Optional dict with ``{"api_key": "sk-...", "model": "gpt-4"}``
        passed to RAGAS.

    Returns
    -------
    EvalResult
        Aggregated metric scores.
    """
    if retrieved_contexts is None:
        retrieved_contexts = contexts  # assume ideal retrieval for offline

    lengths = {len(lst) for lst in (queries, expected_answers, contexts, actual_answers, retrieved_contexts)}
    if len(lengths) > 1:
        raise ValueError(
            f"All input lists must have the same length. Got: "
            f"queries={len(queries)}, expected_answers={len(expected_answers)}, "
            f"contexts={len(contexts)}, actual_answers={len(actual_answers)}, "
            f"retrieved_contexts={len(retrieved_contexts)}"
        )

    samples = [
        EvalSample(
            query=q,
            expected_answer=ea,
            contexts=ctx,
            actual_answer=aa,
            retrieved_contexts=rc,
        )
        for q, ea, ctx, aa, rc in zip(
            queries, expected_answers, contexts, actual_answers, retrieved_contexts
        )
    ]

    evaluator = RAGASEvaluator(llm_config=llm_config)
    return evaluator.evaluate_samples(samples)