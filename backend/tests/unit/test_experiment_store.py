import shutil
from pathlib import Path
from backend.experiments.models import Campaign, StrategyType, TrialResult, TrialStatus
from backend.experiments.store import JSONExperimentStore


def test_json_experiment_store(tmp_path: Path):
    store = JSONExperimentStore(base_dir=tmp_path)

    campaign = Campaign(
        campaign_id="test_camp_1",
        name="Unit Test Campaign",
    )
    store.save_campaign(campaign)

    loaded = store.get_campaign("test_camp_1")
    assert loaded is not None
    assert loaded.name == "Unit Test Campaign"
    assert len(loaded.trials) == 0

    trial = TrialResult(
        trial_id="t1",
        campaign_id="test_camp_1",
        trial_number=1,
        strategy=StrategyType.DEFAULT,
        parameters={"top_k": 5},
        objective_score=0.82,
        mean_quality=0.85,
        p95_latency_ms=800.0,
    )
    store.log_trial("test_camp_1", trial)

    updated = store.get_campaign("test_camp_1")
    assert len(updated.trials) == 1
    assert updated.trials[0].trial_id == "t1"
    assert updated.best_trial_id == "t1"
