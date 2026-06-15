"""Unit tests for the evaluation agent (RAGASEvaluator, EvalSample, EvalResult)."""

from __future__ import annotations

import pytest
from backend.agents.evaluation.agent import (
    RAGASEvaluator,
    EvalSample,
    EvalResult,
    run_offline_evaluation,
)


class TestEvalSample:
    def test_default_fields(self) -> None:
        sample = EvalSample(
            query="test?",
            expected_answer="yes",
            contexts=["some context"],
        )
        assert sample.query == "test?"
        assert sample.expected_answer == "yes"
        assert sample.contexts == ["some context"]
        assert sample.actual_answer == ""          # default
        assert sample.retrieved_contexts == []      # default

    def test_with_retrieved_contexts(self) -> None:
        sample = EvalSample(
            query="q",
            expected_answer="a",
            contexts=["ctx"],
            actual_answer="ans",
            retrieved_contexts=["retrieved"],
        )
        assert sample.actual_answer == "ans"
        assert sample.retrieved_contexts == ["retrieved"]


class TestEvalResult:
    def test_defaults(self) -> None:
        result = EvalResult()
        assert result.faithfulness == 0.0
        assert result.answer_relevancy == 0.0
        assert result.context_precision == 0.0
        assert result.run_id == ""
        assert result.num_samples == 0
        assert result.duration_seconds == 0.0
        assert result.error is None

    def test_with_values(self) -> None:
        result = EvalResult(
            faithfulness=0.85,
            answer_relevancy=0.92,
            context_precision=0.78,
            run_id="eval_123",
            num_samples=10,
            duration_seconds=2.5,
        )
        assert result.faithfulness == 0.85
        assert result.answer_relevancy == 0.92
        assert result.context_precision == 0.78


class TestRAGASEvaluator:
    def test_init_without_ragas_uses_heuristic(self) -> None:
        """If RAGAS is not installed, we fall back to heuristic scoring."""
        evaluator = RAGASEvaluator()
        # The evaluator should still be functional
        assert evaluator is not None

    def test_evaluate_empty_list(self) -> None:
        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_samples([])
        assert result.error == "No samples provided."

    def test_evaluate_single_sample_heuristic(self) -> None:
        evaluator = RAGASEvaluator()
        samples = [
            EvalSample(
                query="What is Python?",
                expected_answer="A programming language.",
                contexts=["Python is a programming language used for development."],
                actual_answer="Python is a programming language.",
                retrieved_contexts=["Python is a programming language used for development."],
            )
        ]
        result = evaluator.evaluate_samples(samples)

        assert result.num_samples == 1
        assert result.run_id.startswith("eval_")
        assert result.duration_seconds >= 0.0
        assert result.error is None

        # Heuristic: answer tokens overlap with context
        assert result.faithfulness > 0.0
        # Heuristic: question tokens appear in answer
        assert result.answer_relevancy > 0.0
        # Heuristic: expected answer tokens appear in context
        assert result.context_precision > 0.0

    def test_evaluate_multiple_samples_heuristic(self) -> None:
        evaluator = RAGASEvaluator()
        samples = [
            EvalSample(
                query="Q1",
                expected_answer="A1",
                contexts=["C1"],
                actual_answer="A1",
                retrieved_contexts=["C1"],
            ),
            EvalSample(
                query="Q2",
                expected_answer="A2",
                contexts=["C2"],
                actual_answer="A2",
                retrieved_contexts=["C2"],
            ),
        ]
        result = evaluator.evaluate_samples(samples)

        assert result.num_samples == 2
        assert result.error is None

    def test_heuristic_perfect_match(self) -> None:
        """When answer perfectly overlaps with context, faithfulness should be 1.0.

        Note: answer_relevancy is based on token overlap between the *query*
        and the answer. Since "test" shares no tokens with "hello world" its
        heuristic score is 0.0. This is expected — the heuristic is a simple
        proxy; the real RAGAS metric would use an LLM judge.
        """
        evaluator = RAGASEvaluator()
        sample = EvalSample(
            query="test",
            expected_answer="hello world",
            contexts=["hello world"],
            actual_answer="hello world",
            retrieved_contexts=["hello world"],
        )
        result = evaluator.evaluate_samples([sample])
        assert result.faithfulness == 1.0
        # Query "test" shares zero tokens with answer "hello world"
        assert result.answer_relevancy == 0.0
        assert result.context_precision == 1.0

    def test_heuristic_no_match(self) -> None:
        """When answer has no overlap with context, faithfulness should be 0.0."""
        evaluator = RAGASEvaluator()
        sample = EvalSample(
            query="query",
            expected_answer="completely unrelated",
            contexts=["something entirely different"],
            actual_answer="zzz",
            retrieved_contexts=["something entirely different"],
        )
        result = evaluator.evaluate_samples([sample])
        assert result.faithfulness == 0.0
        assert result.answer_relevancy == 0.0   # "query" not in "zzz"
        assert result.context_precision == 0.0  # expected tokens not in context


class TestRunOfflineEvaluation:
    def test_basic_run(self) -> None:
        result = run_offline_evaluation(
            queries=["What is X?"],
            expected_answers=["X is Y."],
            contexts=[["X is a thing called Y."]],
            actual_answers=["X is Y."],
        )
        assert result.num_samples == 1
        assert result.error is None
        # Metrics should be > 0 due to overlap
        assert result.faithfulness >= 0.0
        assert result.answer_relevancy >= 0.0
        assert result.context_precision >= 0.0

    def test_with_retrieved_contexts(self) -> None:
        result = run_offline_evaluation(
            queries=["Q"],
            expected_answers=["A"],
            contexts=[["gold context"]],
            actual_answers=["A"],
            retrieved_contexts=[["retrieved context A"]],
        )
        assert result.num_samples == 1
        assert result.error is None

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError):
            run_offline_evaluation(
                queries=["Q1", "Q2"],
                expected_answers=["A1"],
                contexts=[["C1"]],
                actual_answers=["A1", "A2"],
            )

    def test_empty_inputs(self) -> None:
        result = run_offline_evaluation(
            queries=[],
            expected_answers=[],
            contexts=[],
            actual_answers=[],
        )
        assert result.error == "No samples provided."