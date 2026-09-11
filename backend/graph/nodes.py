import asyncio
import time
from typing import Any, Dict, Callable, Awaitable
from backend.graph.state import RAGState, RetrievedChunk, GenerationResult
from backend.core.logging import get_logger
from backend.core.config import settings
from backend.graph.complexity import compute_complexity, compute_complexity_llm, adaptive_k, select_rerank_top_k
from backend.storage.tenant import resolve_tenant_id
from backend.storage.tenant import METADATA_CHUNK_KEY, METADATA_DOCUMENT_KEY

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Factory functions — each takes a ServiceContainer and returns a closure
# that LangGraph can call with (RAGState) -> Dict[str, Any].
# No module-level svc dependency.
# ---------------------------------------------------------------------------

def create_intake_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        start_time = time.time()
        logger.info("Node: Intake", query=state.query)

        original_query = state.query

        # Parallel intake enrichment (Phase 1B)
        async def _get_history():
            try:
                return await deps.session_memory.get_history(state.session_id, limit=5)
            except Exception as e:
                logger.debug("Session memory get_history failed", error=str(e))
                return []

        async def _get_insights():
            if not deps.memory_agent:
                return []
            try:
                return await asyncio.to_thread(deps.memory_agent.retrieve_past_insights, state.query)
            except Exception as e:
                logger.debug("Past insights retrieval skipped", error=str(e))
                return []

        history, past_insights = await asyncio.gather(_get_history(), _get_insights())
        history_str = "\n".join([f"{m['role']}: {m['content']}" for m in history]) if history else ""

        result = {
            "current_phase": "intake",
            "retry_count": 0,
            "error_log": [],
            "original_query": original_query,
            "history_context": history_str,
            "query": state.query,
            "long_term_insights": past_insights,
        }

        if getattr(deps, "telemetry_collector", None):
            await deps.telemetry_collector.log_trace(
                session_id=state.session_id,
                query=state.query,
                phase="intake",
                agent_name="System",
                input_data={"original_query": state.query},
                output_data=result,
                latency_ms=(time.time() - start_time) * 1000,
            )

        return result

    return node


def create_planning_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        logger.info("Node: Planning")

        # Phase 3C — Adaptive complexity classification
        if settings.COMPLEXITY_USE_LLM and hasattr(deps, "llm_client"):
            complexity_score = compute_complexity_llm(state.query, deps.llm_client)
        else:
            complexity_score = compute_complexity(state.query)

        target_k = adaptive_k(complexity_score)

        logger.info(
            "Adaptive retrieval",
            complexity_score=complexity_score,
            target_k=target_k,
        )

        strategy = "DIRECT" if target_k <= 3 else "HYBRID"
        plan = {"is_complex": complexity_score > 0.3, "strategy": strategy, "reasoning": f"Adaptive: score={complexity_score:.2f}, k={target_k}"}

        # If the query is complex enough, also invoke the planner for deeper analysis
        if complexity_score > 0.7 and hasattr(deps, "planner") and deps.planner:
            deep_plan = await deps.planner.create_plan(state.query)
            plan["sub_queries"] = deep_plan.get("sub_queries", [])

        return {
            "planner_plan": plan,
            "complexity_score": complexity_score,
            "target_k": target_k,
            "current_phase": "planning",
        }

    return node


def create_retrieval_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        start_time = time.time()
        query = state.rewritten_query or state.query
        k = state.target_k or 5
        rerank_top_k = select_rerank_top_k(k)
        logger.info("Node: Retrieval", query=query, target_k=k, rerank_top_k=rerank_top_k)

        tid = resolve_tenant_id(state.tenant_id)
        fused_results = await deps.hybrid_retriever.retrieve(
            query,
            k=k,
            tenant_id=tid,
            user_uuid=tid,
            session_id=state.session_id,
        )

        reranked_results = await deps.reranker.rerank(query, fused_results, top_k=rerank_top_k)

        chunks = []
        for res in reranked_results:
            metadata = res.get("metadata", {})
            content = res["content"]
            chunk_id = res.get("chunk_id") or metadata.get(METADATA_CHUNK_KEY, "")
            document_id = metadata.get(METADATA_DOCUMENT_KEY, "")
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    content=content,
                    score=res.get("rerank_score", res.get("score", 0.0)),
                    source=document_id or metadata.get("file_name", "unknown"),
                    metadata=metadata,
                    distance=res.get("distance", None),
                )
            )

        # Check for knowledge absence (Phase 1A fast-fail) — distance-aware
        # RRF scores are ~0.016, so threshold 0.5 never matches; use cosine distance when available.
        # For pgvector: distance = 1 - cosine_similarity, 0=identical, 2=opposite.
        # RELEVANCE_THRESHOLD is cosine similarity, so convert to distance threshold.
        if len(chunks) == 0:
            has_relevant = False
        else:
            # If any chunk has a vector distance, use that for relevance
            dist_threshold = 1.0 - float(settings.RELEVANCE_THRESHOLD)  # e.g. 0.5 -> 0.5 distance
            # Clamp to sensible bounds: at least 0.65 to avoid over-filtering moderate matches,
            # at most 0.85 to avoid accepting pure noise
            dist_threshold = max(0.65, min(dist_threshold, 0.85))
            has_relevant = False
            # Determine score threshold for non-vector results
            rerank_provider = getattr(settings, "RERANKER_PROVIDER", "none") or "none"
            is_cross_encoder = rerank_provider.lower() not in ("none", "", "noop")
            score_thresh = float(settings.RELEVANCE_THRESHOLD) if is_cross_encoder else 0.008
            for c in chunks:
                if c.distance is not None:
                    try:
                        if float(c.distance) <= dist_threshold:
                            has_relevant = True
                            break
                    except Exception:
                        pass
                else:
                    if c.score >= score_thresh:
                        has_relevant = True
                        break
            # Edge: if no distance and all RRF but corpus non-empty, treat as relevant if we have any chunk
            # (prevents false fast-fail on small corpora with NoOp reranker)
            if not has_relevant and all(c.distance is None for c in chunks):
                # At least one fused result exists — consider relevant
                has_relevant = len(chunks) > 0
        no_relevant = (len(chunks) == 0) or (not has_relevant)

        result: Dict[str, Any] = {
            "retrieved_chunks": chunks,
            "current_phase": "retrieval",
            "chunks_retrieved": len(chunks),
            "target_k": k,  # Preserve for downstream telemetry / debugging
            "no_relevant_chunks": no_relevant,
        }

        if no_relevant:
            logger.info(
                "Fast-fail: no relevant chunks above threshold",
                chunks_count=len(chunks),
                threshold=settings.RELEVANCE_THRESHOLD,
            )
            result["generation_result"] = GenerationResult(
                answer="Information not available in knowledge base.",
                model="none",
            )

        if getattr(deps, "telemetry_collector", None):
            await deps.telemetry_collector.log_trace(
                session_id=state.session_id,
                query=state.query,
                phase="retrieval",
                agent_name="HybridRetriever",
                input_data={"query": query},
                output_data={"chunks_count": len(chunks)},
                latency_ms=(time.time() - start_time) * 1000,
            )

        return result

    return node


def create_generation_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        logger.info("Node: Generation")

        if not state.retrieved_chunks:
            return {
                "generation_result": GenerationResult(
                    answer="I couldn't find any relevant information to answer your question.",
                    model="none",
                ),
                "current_phase": "generation",
            }

        context = [c.content for c in state.retrieved_chunks]

        # Check if a token queue was injected for SSE streaming (Phase 4B).
        # When present, each token is pushed to the queue individually so the
        # SSE stream runner can forward it to the client in real time.
        token_queue: asyncio.Queue | None = state._token_queue

        if token_queue is not None:
            # Streaming path — push tokens to the queue as they arrive.
            full_answer: list[str] = []
            async for token in deps.generator.generate_answer_stream(
                state.query, context, history=state.history_context
            ):
                full_answer.append(token)
                await token_queue.put(token)
            await token_queue.put(None)  # Signal end-of-stream.
            answer = "".join(full_answer)
        else:
            # Non-streaming path — original behaviour.
            result = await deps.generator.generate_answer(
                state.query, context, history=state.history_context
            )
            answer = result["answer"]

        return {
            "generation_result": GenerationResult(
                answer=answer,
                model=deps.generator.client.model,
            ),
            "current_phase": "generation",
        }

    return node


def create_critic_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        logger.info("Node: Critic")

        gen_result = state.generation_result
        if not gen_result or not state.retrieved_chunks:
            return {
                "is_hallucinated": True,
                "grounding_score": 0.0,
                "verification_mode": "no_claims",
                "error_log": ["No generation result or retrieved chunks"],
                "current_phase": "critic",
            }

        context = [c.content for c in state.retrieved_chunks]
        # Critic fast-path for simple queries (Decision 1C / Phase 1C)
        if state.complexity_score < 0.3 and hasattr(deps.critic, "verify_grounding_fast"):
            result = await deps.critic.verify_grounding_fast(
                state.query, gen_result.answer, context, history=state.history_context
            )
        else:
            result = await deps.critic.verify_grounding(
                state.query, gen_result.answer, context, history=state.history_context
            )

        verification_mode = result.get("verification_mode", "claims_verified")
        error_entry = [reason.strip() for reason in [result.get("reasoning", "")] if reason.strip()]

        return {
            "grounding_score": result.get("grounding_score", 0.0),
            "is_hallucinated": result.get("is_hallucinated", False),
            "verification_mode": verification_mode,
            "healing_target": result.get("healing_target", ""),
            "error_log": error_entry if result.get("is_hallucinated") else [],
            "current_phase": "critic",
        }

    return node


def create_healing_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        logger.info(
            "Node: Healing",
            retry_count=state.retry_count,
            healing_target=state.healing_target,
        )

        error_context = "\n".join(state.error_log)
        rewritten = await deps.rewriter.rewrite_query(
            state.query,
            error_context,
            healing_target=state.healing_target,
        )

        return {
            "rewritten_query": rewritten,
            "retry_count": state.retry_count + 1,
            "current_phase": "healing",
            "retrieved_chunks": [],
        }

    return node


def create_evaluation_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        logger.info("Node: Evaluation")

        metrics = deps.evaluator.evaluate_response(state)
        return {
            "grounding_score": metrics["composite_score"],
            "current_phase": "evaluation",
        }

    return node


def create_output_node(deps) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def node(state: RAGState) -> Dict[str, Any]:
        logger.info("Node: Output")

        gen_result = state.generation_result
        answer = (
            state.final_answer
            or (gen_result.answer if gen_result else None)
            or ("Information not available in knowledge base." if state.no_relevant_chunks else "No answer generated.")
        )

        # In fast-fail streaming path, emit token directly if not streamed during generation
        if state.no_relevant_chunks and getattr(state, "_token_queue", None) is not None:
            await state._token_queue.put(answer)

        await deps.session_memory.add_message(
            state.session_id, "user", state.original_query or state.query
        )
        await deps.session_memory.add_message(
            state.session_id, "assistant", answer
        )

        # Async cache write (non-blocking but await if possible)
        try:
            if hasattr(deps.query_cache, "cache_query_async"):
                await deps.query_cache.cache_query_async(
                    state.original_query or state.query,
                    answer,
                    {"grounding_score": state.grounding_score},
                    tenant_id=state.tenant_id,
                )
            else:
                deps.query_cache.cache_query(
                    state.original_query or state.query,
                    answer,
                    {"grounding_score": state.grounding_score},
                    tenant_id=state.tenant_id,
                )
        except Exception as e:
            logger.debug("Cache store failed in output node", error=str(e))

        return {"final_answer": answer, "current_phase": "completed"}

    return node