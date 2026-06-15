import asyncio
from typing import Optional, Annotated
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.core.logging import get_logger

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

        result = await run_rag_pipeline(
            graph,
            svc,
            request.query,
            user_session_id,
            tenant_id=tenant_id,
            user_uuid=user_uuid,
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
        try:
            async for sse_event in stream_rag_pipeline(
                graph,
                svc,
                request.query,
                user_session_id,
                tenant_id=tenant_id,
                user_uuid=user_uuid,
            ):
                yield sse_event
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
