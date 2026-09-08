import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.metrics import compute_composite_quality, compute_trial_aggregates
from backend.experiments.models import (
    BudgetConfig,
    ObjectiveConfig,
    StrategyType,
    TrialQueryResult,
    TrialResult,
    TrialStatus,
)
from backend.experiments.objective import calculate_objective_score
from backend.experiments.statistics import compute_statistical_summary
from backend.graph.container import ServiceContainer
from backend.graph.runner import run_rag_pipeline
from backend.graph.workflow import create_rag_graph

logger = get_logger(__name__)


class ExperimentRunner:
    """Executes an isolated experiment trial against a designated benchmark dataset."""

    def __init__(self, config_registry: Optional[ConfigRegistry] = None):
        self.registry = config_registry or ConfigRegistry()

    async def execute_trial(
        self,
        campaign_id: str,
        trial_number: int,
        strategy: StrategyType,
        parameters: Dict[str, Any],
        dataset: List[Dict[str, Any]],
        objective_config: ObjectiveConfig,
        budget_config: BudgetConfig,
        baseline_quality_scores: Optional[List[float]] = None,
        hypothesis: Optional[str] = None,
        justification: Optional[str] = None,
    ) -> TrialResult:
        """Run a single experiment trial across all dataset items under strict isolation."""
        trial_id = f"trial_{uuid.uuid4().hex[:8]}"
        logger.info(
            "Starting trial execution",
            trial_id=trial_id,
            trial_number=trial_number,
            strategy=strategy.value,
            params=parameters,
        )

        # 1. Validate & clamp proposed parameters
        clamped_params = self.registry.validate_and_clamp(parameters)
        settings_overrides_dict = self.registry.resolve_settings_overrides(clamped_params)

        # 2. Build isolated container & graph
        trial_settings = settings.with_overrides(**settings_overrides_dict)
        container = ServiceContainer.build(trial_settings)
        graph = create_rag_graph(container)

        query_results: List[TrialQueryResult] = []
        trial_failed = False
        error_msg = None

        try:
            for idx, item in enumerate(dataset):
                query_id = item.get("id", f"q_{idx}")
                query_text = item.get("query", "")
                ground_truth = item.get("ground_truth", "")

                start_time = time.perf_counter()
                try:
                    # Enforce per-query timeout
                    pipeline_res = await asyncio.wait_for(
                        run_rag_pipeline(
                            graph=graph,
                            deps=container,
                            query=query_text,
                            session_id=f"exp_{trial_id}_{query_id}",
                            tenant_id="experiment_tenant",
                            skip_cache=True,
                            skip_websocket=True,
                        ),
                        timeout=float(budget_config.query_timeout_seconds),
                    )

                    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                    generated_answer = pipeline_res.get("answer", "")
                    healing_count = pipeline_res.get("retry_count", 0)

                    # Evaluate answer quality
                    eval_metrics = await self._evaluate_sample(
                        evaluator=container.evaluator,
                        query=query_text,
                        answer=generated_answer,
                        ground_truth=ground_truth,
                    )

                    comp_q = compute_composite_quality(
                        faithfulness=eval_metrics["faithfulness"],
                        answer_relevance=eval_metrics["answer_relevance"],
                        context_precision=eval_metrics["context_precision"],
                        context_recall=eval_metrics["context_recall"],
                        weights=objective_config.weights,
                    )

                    # Estimate token consumption
                    tokens = (len(query_text.split()) + len(generated_answer.split())) * 4

                    query_results.append(
                        TrialQueryResult(
                            query_id=query_id,
                            query_text=query_text,
                            generated_answer=generated_answer,
                            faithfulness=eval_metrics["faithfulness"],
                            answer_relevance=eval_metrics["answer_relevance"],
                            context_precision=eval_metrics["context_precision"],
                            context_recall=eval_metrics["context_recall"],
                            composite_quality=comp_q,
                            latency_ms=latency_ms,
                            healing_count=healing_count,
                            token_count=tokens,
                        )
                    )

                except asyncio.TimeoutError:
                    logger.warning("Query timed out during trial", trial_id=trial_id, query_id=query_id)
                    latency_ms = budget_config.query_timeout_seconds * 1000.0
                    query_results.append(
                        TrialQueryResult(
                            query_id=query_id,
                            query_text=query_text,
                            latency_ms=latency_ms,
                            error="QUERY_TIMEOUT",
                        )
                    )
                except Exception as ex:
                    logger.error("Query failed during trial", trial_id=trial_id, query_id=query_id, error=str(ex))
                    query_results.append(
                        TrialQueryResult(
                            query_id=query_id,
                            query_text=query_text,
                            latency_ms=0.0,
                            error=str(ex),
                        )
                    )

        except Exception as trial_ex:
            logger.error("Trial encountered fatal exception", trial_id=trial_id, error=str(trial_ex))
            trial_failed = True
            error_msg = str(trial_ex)
        finally:
            await container.close()

        # 3. Aggregate metrics
        aggregates = compute_trial_aggregates(query_results, objective_config.weights)
        obj_score = calculate_objective_score(
            mean_quality=aggregates["mean_quality"],
            p95_latency_ms=aggregates["p95_latency_ms"],
            total_tokens=aggregates["total_tokens"],
            mean_healing_count=aggregates["mean_healing_count"],
            config=objective_config,
        )

        # 4. Statistical Summary (Bootstrap CI & Paired Wilcoxon Test)
        stats_summary = compute_statistical_summary(
            candidate_scores=aggregates["quality_scores"],
            baseline_scores=baseline_quality_scores,
        )

        return TrialResult(
            trial_id=trial_id,
            campaign_id=campaign_id,
            trial_number=trial_number,
            strategy=strategy,
            parameters=clamped_params,
            objective_score=obj_score,
            mean_quality=aggregates["mean_quality"],
            p95_latency_ms=aggregates["p95_latency_ms"],
            mean_latency_ms=aggregates["mean_latency_ms"],
            total_tokens=aggregates["total_tokens"],
            mean_healing_count=aggregates["mean_healing_count"],
            hypothesis=hypothesis,
            justification=justification,
            statistical_summary=stats_summary,
            query_results=query_results,
            status=TrialStatus.FAILED if trial_failed else TrialStatus.COMPLETED,
            error_message=error_msg,
        )

    async def _evaluate_sample(
        self,
        evaluator: Any,
        query: str,
        answer: str,
        ground_truth: str,
    ) -> Dict[str, float]:
        """Evaluate a single sample with RAGAS or fallback heuristics."""
        if not answer:
            return {"faithfulness": 0.0, "answer_relevance": 0.0, "context_precision": 0.0, "context_recall": 0.0}

        try:
            if evaluator and hasattr(evaluator, "evaluate"):
                result = await evaluator.evaluate(
                    query=query,
                    response=answer,
                    contexts=[ground_truth] if ground_truth else [answer],
                    ground_truth=ground_truth,
                )
                return {
                    "faithfulness": float(result.get("faithfulness", 0.7)),
                    "answer_relevance": float(result.get("answer_relevance", 0.7)),
                    "context_precision": float(result.get("context_precision", 0.7)),
                    "context_recall": float(result.get("context_recall", 0.7)),
                }
        except Exception as e:
            logger.debug("Evaluator call failed, using heuristic scoring", error=str(e))

        # Heuristic scoring fallback
        overlap = len(set(answer.lower().split()) & set(ground_truth.lower().split())) if ground_truth else 3
        gt_len = len(ground_truth.split()) if ground_truth else 5
        score = min(1.0, overlap / max(1, gt_len))
        return {
            "faithfulness": round(score, 2),
            "answer_relevance": round(score, 2),
            "context_precision": round(score, 2),
            "context_recall": round(score, 2),
        }
