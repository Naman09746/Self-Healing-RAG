from unittest.mock import AsyncMock, patch
import pytest
from backend.experiments.models import (
    BudgetConfig,
    ObjectiveConfig,
    StrategyType,
    TrialStatus,
)
from backend.experiments.runner import ExperimentRunner


@pytest.mark.asyncio
async def test_experiment_runner_mock_execution():
    runner = ExperimentRunner()

    dataset = [
        {"id": "q1", "query": "What is RAG?", "ground_truth": "RAG is retrieval augmented generation"},
        {"id": "q2", "query": "What is Chroma?", "ground_truth": "Chroma is an open source vector database"},
    ]

    mock_pipeline_res = {
        "query": "What is RAG?",
        "answer": "RAG is retrieval augmented generation in LLMs.",
        "chunks_retrieved": 3,
        "status": "completed",
        "grounding_score": 0.9,
        "retry_count": 0,
    }

    with patch("backend.experiments.runner.run_rag_pipeline", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_pipeline_res

        result = await runner.execute_trial(
            campaign_id="camp_test",
            trial_number=1,
            strategy=StrategyType.DEFAULT,
            parameters={"top_k": 5, "hybrid_search_alpha": 0.5},
            dataset=dataset,
            objective_config=ObjectiveConfig(),
            budget_config=BudgetConfig(),
            hypothesis="Test default configuration",
        )

        assert result.status == TrialStatus.COMPLETED
        assert len(result.query_results) == 2
        assert result.mean_quality > 0.0
        assert result.statistical_summary is not None
        assert result.statistical_summary.sample_size == 2
