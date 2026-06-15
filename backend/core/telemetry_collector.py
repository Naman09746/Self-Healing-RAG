import time
from typing import Dict, Any, Optional
from backend.storage.db.models import ExecutionTrace, EvaluationMetric
from backend.storage.db.session import AsyncSessionLocal
from backend.core.logging import get_logger

logger = get_logger(__name__)

class TelemetryCollector:
    @staticmethod
    async def log_trace(
        session_id: str,
        query: str,
        phase: str,
        agent_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        latency_ms: float,
        tokens_used: int = 0,
        is_error: bool = False
    ):
        """Asynchronously log an execution trace to Postgres."""
        async with AsyncSessionLocal() as session:
            try:
                trace = ExecutionTrace(
                    session_id=session_id,
                    query=query,
                    phase=phase,
                    agent_name=agent_name,
                    input_data=input_data,
                    output_data=output_data,
                    latency_ms=latency_ms,
                    tokens_used=tokens_used,
                    is_error=is_error
                )
                session.add(trace)
                await session.commit()
            except Exception as e:
                # Silently fail or log warning to avoid cluttering logs during dev
                logger.warning(f"Telemetry skipped: {str(e)}")

    @staticmethod
    async def log_metrics(session_id: str, metrics: Dict[str, float]):
        """Asynchronously log evaluation metrics to Postgres."""
        async with AsyncSessionLocal() as session:
            try:
                eval_metric = EvaluationMetric(
                    session_id=session_id,
                    grounding_score=metrics.get("grounding_score", 0.0),
                    answer_relevance=metrics.get("answer_relevance", 0.0),
                    faithfulness=metrics.get("faithfulness", 0.0),
                    retrieval_precision=metrics.get("retrieval_precision", 0.0)
                )
                session.add(eval_metric)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to save evaluation metrics: {str(e)}")

telemetry_collector = TelemetryCollector()
