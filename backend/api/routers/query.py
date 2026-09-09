import asyncio
import json
import time
from typing import Optional, Annotated
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.core.logging import get_logger
from backend.core.metrics import metrics

from backend.graph.runner import run_rag_pipeline
from backend.graph.stream_runner import stream_rag_pipeline
from backend.api.routers.auth import get_current_user, DBUser

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    session_id: str
    chunks_retrieved: int
    status: str
    grounding_score: float
    retry_count: int
    complexity_score: Optional[float] = 0.0
    verification_mode: Optional[str] = ""
    is_hallucinated: Optional[bool] = False


@router.post("", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    fastapi_request: Request,
    current_user: Annotated[DBUser, Depends(get_current_user)],
):
    """Multi-agent RAG query (Phase 3).

    Tenant identity is derived from the authenticated user's JWT, **not**
    from the request body. This prevents cross-tenant data access attacks.
    The ``user_uuid`` is threaded through the pipeline for audit logging.

    Uses the injected LangGraph and ServiceContainer from ``app.state``,
    built at startup — no module-level singletons.
    """
    try:
        # Read injected resources from app.state (set during lifespan)
        graph = fastapi_request.app.state.rag_graph
        svc = fastapi_request.app.state.svc

        # Isolate session memory by user (use immutable user_uuid, not email)
        user_uuid = current_user.user_uuid
        tenant_id = current_user.tenant_id or user_uuid
        user_session_id = (
            f"{user_uuid}_{request.session_id}"
            if request.session_id
            else f"{user_uuid}_default"
        )

        t0 = time.perf_counter()
        result = await run_rag_pipeline(
            graph,
            svc,
            request.query,
            user_session_id,
            tenant_id=tenant_id,
            user_uuid=user_uuid,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Record dynamic telemetry
        metrics.record_query_result(
            latency_ms=latency_ms,
            grounding_score=result.get("grounding_score", 0.0),
            is_hallucinated=result.get("is_hallucinated", False),
            healing_triggered=result.get("retry_count", 0) > 0,
            cache_hit=result.get("status") == "cached",
        )

        # Clean the session ID prefix for the frontend
        clean_session_id = result["session_id"].replace(f"{user_uuid}_", "")

        return QueryResponse(
            query=result["query"],
            answer=result["answer"],
            session_id=clean_session_id,
            chunks_retrieved=result["chunks_retrieved"],
            status=result.get("status", "completed"),
            grounding_score=result.get("grounding_score", 0.0),
            retry_count=result.get("retry_count", 0),
            complexity_score=result.get("complexity_score", 0.0),
            verification_mode=result.get("verification_mode", ""),
            is_hallucinated=result.get("is_hallucinated", False),
        )
    except Exception as e:
        logger.error("Query failed", error=str(e), user_uuid=current_user.user_uuid)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def query_rag_stream(
    request: QueryRequest,
    fastapi_request: Request,
    current_user: Annotated[DBUser, Depends(get_current_user)],
):
    """Multi-agent RAG query with **server-sent events** (Phase 4B).

    Returns a ``text/event-stream`` response that emits four event types:

    +----------+----------------------------------------------------------+
    | event    | description                                              |
    +==========+==========================================================+
    | ``phase``| Pipeline stage (``intake``, ``planning``, ``retrieval``, |
    |          | ``generation``, ``critic``, ``healing``, ``completed``)  |
    +----------+----------------------------------------------------------+
    | ``token``| An individual decoded text token from the LLM.           |
    +----------+----------------------------------------------------------+
    | ``metadata`` | Final result summary (answer, score, chunk count).   |
    +----------+----------------------------------------------------------+
    | ``error``| Fatal error message.                                     |
    +----------+----------------------------------------------------------+

    Usage (JavaScript / EventSource):
    ```js
    const es = new EventSource("/v1/query/stream");
    es.addEventListener("token", (e) => {
        const data = JSON.parse(e.data);
        console.log(data.token);
    });
    ```

    **Security note:** Tenant identity is derived from the authenticated user's
    JWT, **not** from the request body.
    """
    graph = fastapi_request.app.state.rag_graph
    svc = fastapi_request.app.state.svc

    user_uuid = current_user.user_uuid
    tenant_id = current_user.tenant_id or user_uuid
    user_session_id = (
        f"{user_uuid}_{request.session_id}"
        if request.session_id
        else f"{user_uuid}_default"
    )

    async def event_generator():
        t0 = time.perf_counter()
        last_metadata = None
        try:
            async for sse_event in stream_rag_pipeline(
                graph,
                svc,
                request.query,
                user_session_id,
                tenant_id=tenant_id,
                user_uuid=user_uuid,
            ):
                if sse_event.startswith("event: metadata"):
                    try:
                        lines = sse_event.strip().split("\n")
                        for line in lines:
                            if line.startswith("data: "):
                                last_metadata = json.loads(line[6:])
                    except Exception:
                        pass
                yield sse_event

            latency_ms = (time.perf_counter() - t0) * 1000.0
            grounding_score = last_metadata.get("grounding_score", 0.0) if last_metadata else 0.0
            is_hallucinated = last_metadata.get("is_hallucinated", False) if last_metadata else False
            healing_triggered = (last_metadata.get("retry_count", 0) > 0) if last_metadata else False
            cache_hit = (last_metadata.get("status") == "cached") if last_metadata else False

            metrics.record_query_result(
                latency_ms=latency_ms,
                grounding_score=grounding_score,
                is_hallucinated=is_hallucinated,
                healing_triggered=healing_triggered,
                cache_hit=cache_hit,
            )
        except asyncio.CancelledError:
            logger.info("Client disconnected from SSE stream", session_id=user_session_id)
        except Exception as exc:
            logger.error("SSE stream failed", error=str(exc))
            yield f"event: error\ndata: {exc!s}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )

