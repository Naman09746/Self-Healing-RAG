import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from backend.core.logging import get_logger
from backend.experiments.models import Campaign, TrialResult

logger = get_logger(__name__)

DEFAULT_STORE_DIR = Path("data/experiments")


class ExperimentStore(ABC):
    """Abstract interface for persisting and retrieving experiment campaigns and trials."""

    @abstractmethod
    def save_campaign(self, campaign: Campaign) -> None:
        pass

    @abstractmethod
    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        pass

    @abstractmethod
    def list_campaigns(self) -> List[Campaign]:
        pass

    @abstractmethod
    def log_trial(self, campaign_id: str, trial: TrialResult) -> None:
        pass


class JSONExperimentStore(ExperimentStore):
    """File-system JSON implementation of ExperimentStore."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or DEFAULT_STORE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _campaign_path(self, campaign_id: str) -> Path:
        folder = self.base_dir / campaign_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "campaign.json"

    def save_campaign(self, campaign: Campaign) -> None:
        campaign.updated_at = datetime.now(timezone.utc)
        path = self._campaign_path(campaign.campaign_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(campaign.model_dump_json(indent=2))
        logger.info("Saved campaign checkpoint", campaign_id=campaign.campaign_id, status=campaign.status)

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        path = self._campaign_path(campaign_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Campaign.model_validate(data)

    def list_campaigns(self) -> List[Campaign]:
        campaigns = []
        for campaign_dir in self.base_dir.iterdir():
            if campaign_dir.is_dir():
                manifest = campaign_dir / "campaign.json"
                if manifest.exists():
                    try:
                        with open(manifest, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        campaigns.append(Campaign.model_validate(data))
                    except Exception as e:
                        logger.warning("Failed to load campaign JSON", path=str(manifest), error=str(e))
        return sorted(campaigns, key=lambda c: c.created_at, reverse=True)

    def log_trial(self, campaign_id: str, trial: TrialResult) -> None:
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign with id '{campaign_id}' not found.")

        # Append or replace trial
        existing_idx = next((i for i, t in enumerate(campaign.trials) if t.trial_id == trial.trial_id), None)
        if existing_idx is not None:
            campaign.trials[existing_idx] = trial
        else:
            campaign.trials.append(trial)

        # Update best trial if this trial achieved higher objective score
        if campaign.best_trial_id is None:
            campaign.best_trial_id = trial.trial_id
        else:
            best_trial = next((t for t in campaign.trials if t.trial_id == campaign.best_trial_id), None)
            if best_trial is None or trial.objective_score > best_trial.objective_score:
                campaign.best_trial_id = trial.trial_id

        # Also write standalone trial JSON for easy inspection
        trial_file = self.base_dir / campaign_id / f"trial_{trial.trial_number:03d}_{trial.trial_id}.json"
        with open(trial_file, "w", encoding="utf-8") as f:
            f.write(trial.model_dump_json(indent=2))

        self.save_campaign(campaign)
