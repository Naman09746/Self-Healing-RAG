from typing import Dict, Any, Optional
import uuid
import json
from opentelemetry import trace
from backend.core.logging import get_logger
from backend.core.observability import get_tracer, set_request_id, get_request_id

logger = get_logger(__name__)


async def run_rag_pipeline(
    graph,
    deps,
    query: str,
    session_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_uuid: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the full RAG pipeline via LangGraph with real-time streaming.

    Args:
        graph: A compiled LangGraph (``CompiledStateGraph``) created by
               ``create_rag_graph(deps)``. Injected at call site.
        deps: A ``ServiceContainer`` with all services initialized.
        query: The user's query.
        session_id: Optional session identifier. Generated if not provided.
        tenant_id: Tenant scope for storage-layer isolation. Falls back
                   to the configured default tenant.
        user_uuid: Immutable user UUID for audit logging and session isolation.

    Returns:
        Dict with query, answer, session_id, chunks_retrieved, status,
        grounding_score, and retry_count.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    tracer = get_tracer()
    request_id = get_request_id() or str(uuid.uuid4())

    # Propagate request_id into the tracing context for this pipeline invocation
    set_request_id(request_id)

    with tracer.start_as_current_span("pipeline.run") as pipeline_span:
        pipeline_span.set_attribute("request_id", request_id)
        pipeline_span.set_attribute("query", query[:200])
        pipeline_span.set_attribute("session_id", session_id or "")
        pipeline_span.set_attribute("tenant_id", tenant_id or "")
        pipeline_span.set_attribute("user_uuid", user_uuid or "")

        # Check Semantic Cache — tenant-scoped
        cached = deps.query_cache.get_cached_query(query, tenant_id=tenant_id)
        if cached:
            pipeline_span.set_attribute("cached", True)
            pipeline_span.set_status(trace.Status(trace.StatusCode.OK))
            logger.info("Serving from semantic cache", query=query)
            # Notify WebSocket clients about cache hit
            try:
                from backend.api.routers.websocket import manager
                await manager.send_event(
                    session_id, {"type": "status", "phase": "completed", "source": "cache"}
                )
            except Exception:
                pass  # No WebSocket connection is fine
            return {
                "query": query,
                "answer": cached["answer"],
                "session_id": session_id,
                "chunks_retrieved": 0,
                "status": "cached",
            }

        pipeline_span.set_attribute("cached", False)

        initial_state = {
            "query": query,
            "session_id": session_id,
            "tenant_id": tenant_id or "",
            "user_uuid": user_uuid or "",
            "retrieved_chunks": [],
            "retry_count": 0,
            "max_retries": 3,
            "error_log": [],
            "grounding_score": 0.0,
            "is_hallucinated": False,
            "is_degraded": False,
            "citations": [],
        }

        logger.info("Executing RAG pipeline", query=query, session_id=session_id)

        final_state = initial_state
        try:
            # Stream events through WebSockets
            from backend.api.routers.websocket import manager

            async for event in graph.astream(initial_state, stream_mode="values"):
                final_state = event
                phase = event.get("current_phase", "unknown")

                await manager.send_event(
                    session_id,
                    {
                        "type": "phase_update",
                        "phase": phase,
                        "retry_count": event.get("retry_count", 0),
                        "grounding_score": event.get("grounding_score", 0.0),
                    },
                )

            pipeline_span.set_attribute("status", final_state.get("current_phase", "unknown"))
            pipeline_span.set_attribute("grounding_score", final_state.get("grounding_score", 0.0))
            pipeline_span.set_attribute("retry_count", final_state.get("retry_count", 0))
            pipeline_span.set_attribute("chunks_retrieved", len(final_state.get("retrieved_chunks", [])))
            pipeline_span.set_status(trace.Status(trace.StatusCode.OK))

            return {
                "query": final_state.get("query", query),
                "answer": final_state.get("final_answer"),
                "session_id": session_id,
                "chunks_retrieved": len(final_state.get("retrieved_chunks", [])),
                "status": final_state.get("current_phase"),
                "grounding_score": final_state.get("grounding_score", 0.0),
                "retry_count": final_state.get("retry_count", 0),
            }
        except Exception as e:
            pipeline_span.record_exception(e)
            pipeline_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error("Pipeline execution failed", error=str(e))
            try:
                from backend.api.routers.websocket import manager
                await manager.send_event(session_id, {"type": "error", "message": str(e)})
            except Exception:
                pass
            raise
