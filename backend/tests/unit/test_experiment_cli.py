from unittest.mock import AsyncMock, patch
from typer.testing import CliRunner
from backend.experiments.cli import app
from backend.experiments.models import Campaign, CampaignStatus, StrategyType

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Autonomous Experiment Scientist" in result.stdout


def test_cli_status_empty():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Recent Campaigns" in result.stdout


def test_cli_run_mocked():
    mock_campaign = Campaign(
        campaign_id="camp_cli_test",
        name="Mock CLI Campaign",
        status=CampaignStatus.COMPLETED,
        baseline_strategy=StrategyType.RANDOM,
    )

    with patch("backend.experiments.orchestrator.ExperimentOrchestrator.run_campaign", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_campaign

        result = runner.invoke(app, ["run", "--max-trials", "2", "--strategy", "random"])
        assert result.exit_code == 0
        assert "camp_cli_test" in result.stdout
