import json
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field

from backend.api.routers.auth import get_current_user, DBUser
from backend.core.logging import get_logger
from backend.experiments.models import (
    BudgetConfig,
    Campaign,
    ObjectiveConfig,
    StrategyType,
)
from backend.experiments.scientist.retrospective import RetrospectiveGenerator
from backend.experiments.store import JSONExperimentStore

router = APIRouter(prefix="/experiments", tags=["experiments"])
logger = get_logger(__name__)

store = JSONExperimentStore()
_orchestrator = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from backend.experiments.orchestrator import ExperimentOrchestrator
        _orchestrator = ExperimentOrchestrator(store=store)
    return _orchestrator


class StartCampaignRequest(BaseModel):
    name: str = "aes_optimization_campaign"
    strategy: str = "scientist"
    max_trials: int = Field(default=5, ge=1, le=50)
    p95_sla: float = Field(default=2000.0, gt=0.0)
    dataset_version: str = "dataset_v1"


def _load_eval_dataset(dataset_version: str = "dataset_v1") -> List[Dict[str, Any]]:
    dataset_path = Path(f"data/eval/{dataset_version}.json")
    if not dataset_path.exists():
        dataset_path = Path("data/eval/dataset_v1.json")
    if not dataset_path.exists():
        return []
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [d for d in data if d.get("status") != "candidate" or d.get("human_reviewed") is True]


@router.get("/campaigns")
async def list_campaigns(
    current_user: Annotated[DBUser, Depends(get_current_user)]
):
    """List all experiment campaigns in descending chronological order."""
    campaigns = store.list_campaigns()
    return [c.model_dump() for c in campaigns]


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    current_user: Annotated[DBUser, Depends(get_current_user)]
):
    """Retrieve full details of a specific campaign by ID."""
    campaign = store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found",
        )
    return campaign.model_dump()


@router.get("/campaigns/{campaign_id}/report")
async def get_campaign_report(
    campaign_id: str,
    current_user: Annotated[DBUser, Depends(get_current_user)]
):
    """Retrieve retrospective markdown report for a campaign."""
    campaign = store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found",
        )
    report_file = store.base_dir / campaign_id / "retrospective.md"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return f.read()
    return RetrospectiveGenerator.generate_markdown_report(campaign)


@router.post("/campaigns", status_code=status.HTTP_202_ACCEPTED)
async def start_campaign(
    req: StartCampaignRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[DBUser, Depends(get_current_user)],
):
    """Launch an autonomous experimentation campaign in the background."""
    try:
        strat_enum = StrategyType(req.strategy.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy '{req.strategy}'. Choose from: default, random, grid, bayesian, scientist",
        )

    dataset = _load_eval_dataset(req.dataset_version)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation dataset is empty or not found",
        )

    objective = ObjectiveConfig(max_p95_latency_ms=req.p95_sla)
    budget = BudgetConfig(max_experiments=req.max_trials)

    async def _run_bg():
        try:
            orch = get_orchestrator()
            await orch.run_campaign(
                name=req.name,
                dataset=dataset,
                strategy=strat_enum,
                objective=objective,
                budget=budget,
                dataset_version=req.dataset_version,
            )
        except Exception as e:
            logger.error("Background campaign execution failed", error=str(e))

    background_tasks.add_task(_run_bg)
    return {
        "status": "accepted",
        "message": f"Campaign '{req.name}' queued for execution with strategy '{req.strategy}'",
        "trials_budget": req.max_trials,
    }
