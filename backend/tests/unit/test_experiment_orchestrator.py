from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from backend.experiments.models import (
    BudgetConfig,
    CampaignStatus,
    ObjectiveConfig,
    StrategyType,
    TrialResult,
    TrialStatus,
)
from backend.experiments.orchestrator import ExperimentOrchestrator
from backend.experiments.store import JSONExperimentStore


@pytest.mark.asyncio
async def test_orchestrator_campaign_execution(tmp_path: Path):
    store = JSONExperimentStore(base_dir=tmp_path)
    orchestrator = ExperimentOrchestrator(store=store)

    dataset = [
        {"id": "q1", "query": "Test query 1", "ground_truth": "Answer 1"},
    ]

    async def fake_execute(*args, **kwargs):
        trial_num = kwargs.get("trial_number", 0)
        return TrialResult(
            trial_id=f"mock_trial_{trial_num}",
            campaign_id="test_camp",
            trial_number=trial_num,
            strategy=kwargs.get("strategy", StrategyType.DEFAULT),
            parameters=kwargs.get("parameters", {"top_k": 5}),
            objective_score=0.85,
            mean_quality=0.88,
            p95_latency_ms=750.0,
            status=TrialStatus.COMPLETED,
        )

    with patch.object(orchestrator.runner, "execute_trial", side_effect=fake_execute) as mock_exec:

        campaign = await orchestrator.run_campaign(
            name="Test Campaign",
            dataset=dataset,
            strategy=StrategyType.RANDOM,
            budget=BudgetConfig(max_experiments=3),
        )

        assert campaign.status == CampaignStatus.COMPLETED
        assert len(campaign.trials) == 3
        assert (tmp_path / campaign.campaign_id / "campaign.json").exists()
        assert (tmp_path / campaign.campaign_id / "retrospective.md").exists()


@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker(tmp_path: Path):
    store = JSONExperimentStore(base_dir=tmp_path)
    orchestrator = ExperimentOrchestrator(store=store)

    dataset = [{"id": "q1", "query": "Test", "ground_truth": "Ans"}]

    failed_trial = TrialResult(
        trial_id="failed_t",
        campaign_id="c_fail",
        trial_number=1,
        strategy=StrategyType.RANDOM,
        parameters={},
        status=TrialStatus.FAILED,
    )

    with patch.object(orchestrator.runner, "execute_trial", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = failed_trial

        campaign = await orchestrator.run_campaign(
            name="Circuit Breaker Test",
            dataset=dataset,
            strategy=StrategyType.RANDOM,
            budget=BudgetConfig(max_experiments=5, max_consecutive_failures=2),
        )

        assert campaign.status == CampaignStatus.FAILED_CIRCUIT_BREAKER
