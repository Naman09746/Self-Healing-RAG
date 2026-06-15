"""
Async generator that drives the LangGraph pipeline and yields
Server-Sent Event (SSE) payloads — token-by-token during generation,
phase updates during retrieval/verification, and a final metadata event.

Architecture
------------
The generation node pushes tokens into an ``asyncio.Queue`` stored on
``RAGState._token_queue``.  The stream runner runs the graph concurrently
with a token consumer and merges two event sources onto a single
``event_queue``:

+---------------------------------+-----------------------------------------+
| Source                          | Events                                  |
+=================================+=========================================+
| ``graph.astream()``             | phase changes via ``current_phase``     |
+---------------------------------+-----------------------------------------+
| ``RAGState._token_queue``       | token-by-token generation output        |
+---------------------------------+-----------------------------------------+

Client disconnects surface as ``asyncio.CancelledError``.
"""

from __future__ import annotations

import json
import asyncio
from typing import AsyncGenerator, Any

from backend.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def _sse(event: str, data: dict[str, Any]) -> str:
    """Build a single SSE text frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def stream_rag_pipeline(
    graph: Any,
    deps: Any,
    query: str,
    session_id: str | None = None,
    *,
    tenant_id: str | None = None,
    user_uuid: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE-encoded events while executing the pipeline.

    Event types
    -----------
    ``phase``
        Emitted on every graph state snapshot.  Data: ``current_phase``,
        ``retry_count``.

    ``token``
        An individual decoded token from the LLM.  Data: ``token``,
        ``session_id``.

    ``metadata``
        Final result summary.  Data: ``session_id``, ``query``, ``answer``,
        ``chunks_retrieved``, ``status``, ``grounding_score``,
        ``retry_count``.

    ``error``
        Fatal error.  Data: ``message``.

    The caller **must** wrap iteration in ``try/except asyncio.CancelledError``.
    """
    from backend.graph.state import RAGState

    # ---- cache check ----------------------------------------------------

    cached = deps.query_cache.get_cached_query(query, tenant_id=tenant_id)
    if cached:
        logger.info("Serving from semantic cache (stream)", query=query)
        yield _sse("phase", {"phase": "cache_hit", "retry_count": 0})
        yield _sse("token", {"token": cached["answer"], "session_id": session_id})
        yield _sse(
            "metadata",
            {
                "session_id": session_id,
                "query": query,
                "answer": cached["answer"],
                "chunks_retrieved": 0,
                "status": "cached",
                "grounding_score": 0.0,
                "retry_count": 0,
            },
        )
        return

    # ---- token queue ----------------------------------------------------
    token_queue: asyncio.Queue[str | None] = asyncio.Queue()

    state = RAGState(
        query=query,
        session_id=session_id,
        tenant_id=tenant_id or "",
        user_uuid=user_uuid or "",
    )
    # Inject the token queue as a private attribute (asyncio.Queue is not
    # pydantic-serializable, so it must be a PrivateAttr).
    state._token_queue = token_queue

    logger.info("Streaming RAG pipeline (astream)", query=query, session_id=session_id)

    # ---- concurrent execution -------------------------------------------
    final_state: dict[str, Any] | None = None
    graph_done = asyncio.Event()

    # Single merged event queue: both phase and token producers push into
    # this queue.  ``None`` sentinels signal that a producer is done.
    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run_graph() -> None:
        """Drive the RAG graph via astream, pushing phase events."""
        nonlocal final_state
        try:
            async for step in graph.astream(state, stream_mode="values"):
                final_state = step
                phase = step.get("current_phase", "")
                if phase:
                    await event_queue.put(
                        _sse("phase", {
                            "phase": phase,
                            "retry_count": step.get("retry_count", 0),
                        })
                    )
                # If the graph populated a final_answer we're done
                if step.get("final_answer"):
                    break
            # Signal the token consumer that generation is finished
            await token_queue.put(None)
        except asyncio.CancelledError:
            await token_queue.put(None)
            raise
        except Exception:
            await token_queue.put(None)
            raise
        finally:
            await event_queue.put(None)  # signal phase producer done
            graph_done.set()

    async def _consume_tokens() -> None:
        """Pull tokens from the queue and push token events to the merged queue."""
        while True:
            token = await token_queue.get()
            if token is None:
                break
            await event_queue.put(
                _sse("token", {"token": token, "session_id": session_id})
            )
        await event_queue.put(None)  # signal token producer done

    # ---- merge phase events and token events ----------------------------

    async def _merged() -> AsyncGenerator[str, None]:
        graph_task = asyncio.create_task(_run_graph())
        token_task = asyncio.create_task(_consume_tokens())

        try:
            # Count ``None`` sentinels from the two producers.
            producers_done = 0
            while producers_done < 2:
                item = await event_queue.get()
                if item is None:
                    producers_done += 1
                    continue
                yield item
        except asyncio.CancelledError:
            graph_task.cancel()
            token_task.cancel()
            raise
        finally:
            await graph_done.wait()
            # Re-raise any graph/token exception (except CancelledError,
            # which is expected on client disconnect).
            for t in (graph_task, token_task):
                if t.done():
                    exc = t.exception()
                    if exc and not isinstance(exc, asyncio.CancelledError):
                        raise exc

    # ---- run merged stream ----------------------------------------------
    try:
        async for sse_event in _merged():
            yield sse_event
    except asyncio.CancelledError:
        logger.warning("Stream cancelled by client", session_id=session_id)
        yield _sse("error", {"message": "Request cancelled"})
        # Do NOT re-raise — let the generator exit cleanly so the caller
        # can collect the error event.
    except Exception as exc:
        logger.error("Stream pipeline failed", error=str(exc), session_id=session_id)
        yield _sse("error", {"message": str(exc)})

    # ---- final metadata event -------------------------------------------
    if final_state:
        gen_result = final_state.get("generation_result") or {}
        yield _sse(
            "metadata",
            {
                "session_id": session_id,
                "query": final_state.get("query", query),
                "answer": final_state.get("final_answer") or gen_result.get("answer", ""),
                "chunks_retrieved": len(final_state.get("retrieved_chunks", [])),
                "status": final_state.get("current_phase", "completed"),
                "grounding_score": final_state.get("grounding_score", 0.0),
                "retry_count": final_state.get("retry_count", 0),
            },
        )


# re-export for convenience
__all__ = ["stream_rag_pipeline"]