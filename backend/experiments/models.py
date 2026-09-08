from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    DEFAULT = "default"
    RANDOM = "random"
    GRID = "grid"
    BAYESIAN = "bayesian"
    SCIENTIST = "scientist"


class CampaignStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_CIRCUIT_BREAKER = "failed_circuit_breaker"
    CANCELLED = "cancelled"


class TrialStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ObjectiveWeights(BaseModel):
    faithfulness: float = Field(default=0.35, ge=0.0, le=1.0)
    answer_relevance: float = Field(default=0.25, ge=0.0, le=1.0)
    context_precision: float = Field(default=0.20, ge=0.0, le=1.0)
    context_recall: float = Field(default=0.20, ge=0.0, le=1.0)


class ObjectivePenalties(BaseModel):
    latency: float = Field(default=0.0005, ge=0.0, description="Penalty per ms over max_p95_latency_ms")
    cost: float = Field(default=1.0, ge=0.0, description="Penalty multiplier for simulated token cost")
    healing: float = Field(default=0.05, ge=0.0, description="Penalty per self-healing retry")


class ObjectiveConfig(BaseModel):
    name: str = Field(default="balanced_optimization")
    description: str = Field(default="Maximize answer quality while maintaining latency SLAs and minimizing cost")
    max_p95_latency_ms: float = Field(default=2000.0, gt=0.0)
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    penalties: ObjectivePenalties = Field(default_factory=ObjectivePenalties)


class BudgetConfig(BaseModel):
    max_experiments: int = Field(default=10, ge=1, le=100)
    max_total_seconds: int = Field(default=3600, ge=10)
    query_timeout_seconds: int = Field(default=30, ge=1)
    max_tokens_budget: int = Field(default=500000, ge=1000)
    max_consecutive_failures: int = Field(default=3, ge=1)


class CandidateProposal(BaseModel):
    hypothesis: str = Field(..., description="Scientific hypothesis being tested")
    expected_outcome: str = Field(..., description="Expected directional effect on quality/latency/cost")
    parameters: Dict[str, Any] = Field(..., description="Dict of proposed parameter overrides")
    justification: str = Field(..., description="Rationale referencing prior trials or RAG domain mechanics")


class TrialQueryResult(BaseModel):
    query_id: str
    query_text: str
    generated_answer: Optional[str] = None
    faithfulness: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    context_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    context_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    healing_count: int = Field(default=0, ge=0)
    token_count: int = Field(default=0, ge=0)
    error: Optional[str] = None


class StatisticalSummary(BaseModel):
    sample_size: int = Field(default=0)
    mean: float = Field(default=0.0)
    std_dev: float = Field(default=0.0)
    median: float = Field(default=0.0)
    ci_lower_95: float = Field(default=0.0)
    ci_upper_95: float = Field(default=0.0)
    wilcoxon_p_value: Optional[float] = None
    is_statistically_significant: bool = Field(default=False)
    effect_size: Optional[float] = None


class TrialResult(BaseModel):
    trial_id: str
    campaign_id: str
    trial_number: int
    strategy: StrategyType
    parameters: Dict[str, Any]
    objective_score: float = 0.0
    mean_quality: float = 0.0
    p95_latency_ms: float = 0.0
    mean_latency_ms: float = 0.0
    total_tokens: int = 0
    mean_healing_count: float = 0.0
    hypothesis: Optional[str] = None
    justification: Optional[str] = None
    statistical_summary: Optional[StatisticalSummary] = None
    query_results: List[TrialQueryResult] = Field(default_factory=list)
    status: TrialStatus = TrialStatus.COMPLETED
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Campaign(BaseModel):
    campaign_id: str
    name: str
    status: CampaignStatus = CampaignStatus.PENDING
    baseline_strategy: StrategyType = StrategyType.SCIENTIST
    objective: ObjectiveConfig = Field(default_factory=ObjectiveConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    dataset_version: str = "dataset_v1"
    trials: List[TrialResult] = Field(default_factory=list)
    best_trial_id: Optional[str] = None
    consecutive_failures: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
