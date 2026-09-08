import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
from backend.core.logging import get_logger
from backend.experiments.baselines.bayesian import BayesianAdaptiveBaseline
from backend.experiments.baselines.default import DefaultBaseline
from backend.experiments.baselines.grid import GridSearchBaseline
from backend.experiments.baselines.random import RandomSearchBaseline
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.models import (
    BudgetConfig,
    Campaign,
    CampaignStatus,
    ObjectiveConfig,
    StrategyType,
    TrialResult,
    TrialStatus,
)
from backend.experiments.runner import ExperimentRunner
from backend.experiments.scientist.agent import AutonomousScientist
from backend.experiments.scientist.retrospective import RetrospectiveGenerator
from backend.experiments.store import ExperimentStore, JSONExperimentStore

logger = get_logger(__name__)


class ExperimentOrchestrator:
    """Deterministic orchestrator managing campaigns, baselines, budgets, and safety circuit-breakers."""

    def __init__(
        self,
        store: Optional[ExperimentStore] = None,
        registry: Optional[ConfigRegistry] = None,
        runner: Optional[ExperimentRunner] = None,
    ):
        self.store = store or JSONExperimentStore()
        self.registry = registry or ConfigRegistry()
        self.runner = runner or ExperimentRunner(self.registry)
        self.scientist = AutonomousScientist(self.registry)

        # Baseline strategy handlers
        self.default_strategy = DefaultBaseline(self.registry)
        self.random_strategy = RandomSearchBaseline(self.registry)
        self.grid_strategy = GridSearchBaseline(self.registry)
        self.bayesian_strategy = BayesianAdaptiveBaseline(self.registry)

    async def run_campaign(
        self,
        name: str,
        dataset: List[Dict[str, Any]],
        strategy: StrategyType = StrategyType.SCIENTIST,
        objective: Optional[ObjectiveConfig] = None,
        budget: Optional[BudgetConfig] = None,
        dataset_version: str = "dataset_v1",
    ) -> Campaign:
        """Execute a complete experimentation campaign under deterministic budget control."""
        campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
        obj_config = objective or ObjectiveConfig()
        budget_config = budget or BudgetConfig()

        campaign = Campaign(
            campaign_id=campaign_id,
            name=name,
            status=CampaignStatus.RUNNING,
            baseline_strategy=strategy,
            objective=obj_config,
            budget=budget_config,
            dataset_version=dataset_version,
        )
        self.store.save_campaign(campaign)
        logger.info("Initiated experiment campaign", campaign_id=campaign_id, strategy=strategy.value)

        start_time = time.perf_counter()
        consecutive_failures = 0
        baseline_quality_scores: Optional[List[float]] = None

        # ---------------------------------------------------------------------
        # Step 1: Execute Trial 0 (Default Baseline Anchor)
        # ---------------------------------------------------------------------
        logger.info("Executing Trial 0 (Production Baseline)", campaign_id=campaign_id)
        default_params = self.default_strategy.select_next()
        trial_0 = await self.runner.execute_trial(
            campaign_id=campaign_id,
            trial_number=0,
            strategy=StrategyType.DEFAULT,
            parameters=default_params,
            dataset=dataset,
            objective_config=obj_config,
            budget_config=budget_config,
            hypothesis="Evaluate default production baseline configuration",
            justification="Anchor reference point for paired non-parametric statistical tests",
        )
        self.store.log_trial(campaign_id, trial_0)
        campaign = self.store.get_campaign(campaign_id)  # refresh

        baseline_quality_scores = [q.composite_quality for q in trial_0.query_results]

        # ---------------------------------------------------------------------
        # Step 2: Iterative Experimentation Loop
        # ---------------------------------------------------------------------
        for trial_num in range(1, budget_config.max_experiments):
            # Check elapsed time budget
            elapsed = time.perf_counter() - start_time
            if elapsed >= budget_config.max_total_seconds:
                logger.warning("Campaign reached max elapsed time budget", elapsed_seconds=elapsed)
                break

            # Check circuit breaker
            if consecutive_failures >= budget_config.max_consecutive_failures:
                logger.error("Circuit breaker tripped: max consecutive failures reached", count=consecutive_failures)
                campaign.status = CampaignStatus.FAILED_CIRCUIT_BREAKER
                self.store.save_campaign(campaign)
                return campaign

            # Determine candidate parameters & hypothesis based on strategy
            best_trial = next((t for t in campaign.trials if t.trial_id == campaign.best_trial_id), None)
            candidate_params: Dict[str, Any] = {}
            hypothesis: Optional[str] = None
            justification: Optional[str] = None

            if strategy == StrategyType.SCIENTIST:
                proposal = await self.scientist.propose_candidate(
                    objective=obj_config,
                    trial_history=campaign.trials,
                    best_trial=best_trial,
                )
                candidate_params = proposal.parameters
                hypothesis = proposal.hypothesis
                justification = proposal.justification

            elif strategy == StrategyType.RANDOM:
                candidate_params = self.random_strategy.select_next()
                hypothesis = "Uniform random search across valid bounds"
                justification = "Exploratory random sampling"

            elif strategy == StrategyType.GRID:
                candidate_params = self.grid_strategy.select_next(campaign.trials)
                hypothesis = "Cartesian grid exploration"
                justification = "Systematic parameter sweep"

            elif strategy == StrategyType.BAYESIAN:
                candidate_params = self.bayesian_strategy.select_next(campaign.trials)
                hypothesis = "Gaussian Process UCB acquisition"
                justification = "Bayesian surrogate optimization"

            elif strategy == StrategyType.DEFAULT:
                candidate_params = self.default_strategy.select_next()
                hypothesis = "Repeated baseline run"

            # Execute Trial
            trial_result = await self.runner.execute_trial(
                campaign_id=campaign_id,
                trial_number=trial_num,
                strategy=strategy,
                parameters=candidate_params,
                dataset=dataset,
                objective_config=obj_config,
                budget_config=budget_config,
                baseline_quality_scores=baseline_quality_scores,
                hypothesis=hypothesis,
                justification=justification,
            )

            # Record and Check Failure
            if trial_result.status == TrialStatus.FAILED:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            self.store.log_trial(campaign_id, trial_result)
            campaign = self.store.get_campaign(campaign_id)

        # ---------------------------------------------------------------------
        # Step 3: Finalize Campaign
        # ---------------------------------------------------------------------
        campaign.status = CampaignStatus.COMPLETED
        self.store.save_campaign(campaign)

        # Generate and write retrospective report
        report_md = RetrospectiveGenerator.generate_markdown_report(campaign)
        report_path = (self.store.base_dir / campaign_id / "retrospective.md") if hasattr(self.store, "base_dir") else None
        if report_path:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_md)

        logger.info("Campaign completed successfully", campaign_id=campaign_id, total_trials=len(campaign.trials))
        return campaign
