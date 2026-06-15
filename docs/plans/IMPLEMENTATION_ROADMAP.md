# Engineering Execution Plan
## Self-Healing Multi-Agent RAG — Phased Implementation Roadmap

> **6 independent phases**, each sized as a single deployable PR.
> Dependencies flow forward — Phase N must be merged before Phase N+1 begins.
> No phase requires simultaneous deployment across services.

---

## Phase 1: Data Isolation & Identifier Integrity

### Objective
Eliminate cross-tenant data leakage and broken chunk identity. After this phase, every vector operation is scoped to a user/tenant, and every chunk carries a deterministic content-addressed ID that survives healing cycles.

### Issues Fixed
| # | Issue | Severity |
|---|-------|----------|
| 1 | No tenant isolation in vector store operations | CRITICAL |
| 2 | Chunk IDs generated at retrieval time via UUID4 | CRITICAL |
| 5 | Global QueryCache with no tenant scoping | CRITICAL |

---

#### 1A — Tenant Isolation in ChromaDB

**Files affected:**
- `backend/storage/vector/chroma.py` — Add `tenant_id` parameter to `query()` and `add_chunks()`. Append `where={"tenant_id": tenant_id}` to all collection operations.
- `backend/storage/retriever.py` — Propagate `tenant_id` through `retrieve()` to Chroma queries.
- `backend/graph/nodes.py` — Extract `tenant_id` from graph state, pass to `retrieval_node()` and `output_node()`.
- `backend/graph/state.py` — Add `tenant_id: str = ""` field to `RAGState`.
- `backend/api/routers/query.py` — Extract `tenant_id` from authenticated user in request handler.
- `backend/api/routers/ingest.py` — Pass `tenant_id` to ingestion pipeline.

**Architecture changes:**
- `ChromaStore` becomes tenant-aware via metadata filter injection.
- `RAGState` carries tenant context throughout the graph lifecycle.
- `QueryCache` becomes a per-tenant-scoped resource.

**Database migrations:** None.
**API changes:** Ingestion and query endpoints require authenticated tenant context (implicit via JWT).
**Breaking changes:** All existing un-scoped Chroma collections need re-seeding per tenant. Old data in `chroma_data/` will not be accessible from tenant-scoped queries.
**Rollback strategy:** Revert `chroma.py`, `retriever.py`, `nodes.py`, `state.py`, `query.py`, `ingest.py`. Existing data intact in unscoped collections.
**Validation:** Unit test that `ChromaStore.query()` with `tenant_id="A"` does not return documents from `tenant_id="B"`.
**Test plan:** 3 unit tests — (1) tenant isolation enforcement, (2) cross-tenant leak negative test, (3) retriever propagates tenant_id through RRF fusion. Integration test with two ChromaDB tenants.

**Estimated complexity:** 3 / 10
**Estimated risk:** 2 / 10

---

#### 1B — Deterministic Chunk IDs via SHA-256

**Files affected:**
- `backend/storage/vector/chroma.py` — Change `add_chunks()` to generate `sha256(chunk_content).hexdigest()` as default IDs. Accept optional override.
- `backend/graph/nodes.py` — Remove `str(uuid.uuid4())` generation at retrieval time. Use `res.get("id", "")` directly.
- `backend/ingestion/pipeline.py` — Ensure chunk IDs are generated at ingestion time using SHA-256 of content.
- `backend/ingestion/chunker.py` — Return deterministic IDs from chunker.

**Architecture changes:**
- Chunk identity shifts from retrieval-time to ingestion-time.
- Healing cycles can now detect "stuck chunks" by comparing deterministic IDs across cycles.
- Citation system can reference canonical chunk IDs.

**Database migrations:** None (no existing chunk_id joins).
**API changes:** None. Chunk IDs in response metadata become deterministic strings.
**Breaking changes:** Any external system relying on UUID4 chunk IDs for deduplication will see different IDs post-migration. Impact: zero (no external consumers).
**Rollback strategy:** Revert to `str(uuid.uuid4())` fallback in `nodes.py:104`. No data migration needed.
**Validation:** Verify that two identical chunks produce identical IDs. Verify that the retriever response dict contains the ID from the chunker.
**Test plan:** 3 unit tests — (1) same content → same ID, (2) different content → different ID, (3) retriever results include the deterministic ID from ingestion.

**Estimated complexity:** 2 / 10
**Estimated risk:** 1 / 10

---

#### 1C — QueryCache Tenant Scoping

**Files affected:**
- `backend/memory/query_cache.py` — Add `tenant_id` parameter to `get_cached_query()` and `cache_query()`. Store `tenant_id` in metadata. Filter cache lookups by `tenant_id`.
- `backend/graph/nodes.py` — Pass `state.tenant_id` to cache operations in `output_node()`.

**Architecture changes:**
- Query cache becomes a per-tenant resource.
- Cache entries include `tenant_id` in metadata.

**Database migrations:** None (cache is in ChromaDB, which will be re-seeded).
**API changes:** None.
**Breaking changes:** Existing cache entries (if any) become invisible to tenant-scoped lookups.
**Rollback strategy:** Remove tenant_id filtering from cache methods. All entries become visible again.
**Validation:** Unit test: query cache with `tenant_id="A"` does not return entries from `tenant_id="B"`.
**Test plan:** 2 unit tests — (1) cache cross-tenant isolation, (2) same-tenant cache hit.

**Estimated complexity:** 2 / 10
**Estimated risk:** 2 / 10

---

### Phase 1 Summary

| Metric | Value |
|--------|-------|
| Files changed | 8-10 |
| DB migrations | 0 |
| API changes | 0 (implicit via auth context) |
| Breaking changes | Old Chroma collections invisible (re-seed needed) |
| Total complexity | 4 / 10 |
| Total risk | 3 / 10 |
| Estimated effort | 2-3 days |

---

---

## Phase 2: Infrastructure & Concurrency Foundation

### Objective
Replace SQLite with PostgreSQL, remove all module-level singletons, add proper dependency injection, and migrate Redis to async. After this phase, the system can handle concurrent requests without data corruption or event-loop blocking.

### Issues Fixed
| # | Issue | Severity |
|---|-------|----------|
| 3 | Module-level global singleton agents | CRITICAL |
| 4 | Sync Redis calls blocking async event loop | HIGH |
| 6 | SQLite in project root instead of PostgreSQL | HIGH |
| 18 | HS256 JWT with shared secret (partially — prep for RS256) | MEDIUM |

---

#### 2A — PostgreSQL Migration with Connection Pooling

**Files affected:**
- `backend/storage/db/session.py` — Replace SQLite URL with `postgresql+asyncpg://`. Configure `AsyncEngine` with `pool_size=10, max_overflow=20, pool_pre_ping=True`.
- `backend/storage/db/models.py` — Add `__table_args__` with `postgresql_partition_by` for large tables (execution_traces, evaluation_metrics).
- `backend/core/config.py` — Add `DATABASE_URL` setting with Postgres async DSN. Remove SQLite fallback defaults.
- `docker-compose.yml` — Verify Postgres is configured with persistent volume, healthcheck, and restart policy.
- `Makefile` — Add `make db-migrate`, `make db-rollback` targets.
- `pyproject.toml` — Add `asyncpg`, `alembic`, `psycopg2-binary` to dependencies.

**New files:**
- `backend/alembic/` — Initialize Alembic with `alembic init alembic`.
- `backend/alembic/versions/001_initial_schema.py` — Create initial migration.

**Architecture changes:**
- Database URL moves from SQLite to Postgres with connection pooling.
- Alembic manages schema versioning.
- `with` context managers for session lifecycle.

**Database migrations:** Alembic initial migration creates all tables from `models.py`. Data migration from SQLite to Postgres via script (`scripts/migrate_sqlite_to_postgres.py`).
**API changes:** None (DB layer is internal).
**Breaking changes:** Development environments must run Postgres via Docker Compose. SQLite-based `nexus_core.db` becomes read-only artifact.
**Rollback strategy:** Revert `session.py` to SQLite URL. Keep Alembic but don't run migrations. Old `nexus_core.db` remains intact.
**Validation:** All existing smoke tests pass against Postgres. Connection pool health under 10 concurrent requests.
**Test plan:** Integration test that 10 concurrent DB writes succeed without `database is locked` errors.

**Estimated complexity:** 5 / 10
**Estimated risk:** 5 / 10

---

#### 2B — Remove Module-Level Singletons + Add DI

**Files affected:**
- `backend/graph/nodes.py` — Remove all 11 module-level instantiations (lines 21-31). Create factory function `create_graph_nodes()` that accepts initialized dependencies.
- `backend/graph/workflow.py` — Accept dependency injection in `create_rag_graph(deps)`. Remove singleton `rag_graph` at module level.
- `backend/api/routers/query.py` — Create dependencies via FastAPI `Depends()` or lifespan-managed containers.
- `backend/api/main.py` — Register dependency providers in lifespan. Wire graph factory with lifespan-managed dependencies.
- `backend/graph/runner.py` — Accept injected graph at call time rather than importing module-level `rag_graph`.

**Architecture changes:**
- All agents move from module-level singletons to FastAPI `Depends()` or per-request instantiation.
- ChromaClient becomes a lifespan-managed singleton with connection pooling.
- Redis client becomes a lifespan-managed singleton with async connection.
- Postgres session uses existing `AsyncSessionLocal` via `get_db` dependency.
- Graph is compiled once with injected dependencies, stored in `app.state`.

**Database migrations:** None.
**API changes:** None (internal refactor).
**Breaking changes:** Any existing code that `import rag_graph from backend.graph.workflow` will break. All callers must use the injected/dependency-resolved graph.
**Rollback strategy:** Keep old module-level singletons as fallback in a `nodes_legacy.py` that can be swapped back.
**Validation:** Verify that two concurrent requests use separate agent instances (or properly pooled shared instances). Verify that tests can inject mock dependencies.
**Test plan:** 2 integration tests — (1) concurrent requests do not share mutable state, (2) test with mocked ChromaDB returns expected results.

**Estimated complexity:** 6 / 10
**Estimated risk:** 5 / 10

---

#### 2C — Async Redis Migration

**Files affected:**
- `backend/memory/session.py` — Replace `redis.Redis()` with `redis.asyncio.Redis()`. Change `rpush`, `lrange`, `expire`, `delete` to `await` versions.
- `backend/graph/nodes.py` — Add `await` to `session_memory.get_history()`, `session_memory.add_message()` calls.
- `backend/core/config.py` — Add `REDIS_ASYNC_CONNECTION_POOL_SIZE` setting.

**Architecture changes:**
- Redis client becomes async throughout.
- SessionMemory operations no longer block the event loop.

**Database migrations:** None.
**API changes:** None.
**Breaking changes:** None (sync import path unchanged, only internal implementation changes).
**Rollback strategy:** Revert `session.py` to `redis.Redis()` (sync) and remove `await` from calls in `nodes.py`.
**Validation:** 50 concurrent session writes complete within P99 < 200ms.
**Test plan:** Load test: 50 concurrent session writes, measure P99 latency. Unit test with mocked async Redis.

**Estimated complexity:** 3 / 10
**Estimated risk:** 2 / 10

---

### Phase 2 Summary

| Metric | Value |
|--------|-------|
| Files changed | 10-12 |
| DB migrations | 1 (initial Alembic) |
| API changes | 0 |
| Breaking changes | Graph not importable as singleton; callers must use DI |
| Total complexity | 7 / 10 |
| Total risk | 6 / 10 |
| Estimated effort | 5-7 days |

---

---

## Phase 3: Critic Reliability & Retrieval Intelligence

### Objective
Fix the hallucination detection system: eliminate false positives from empty-claim detection, implement 4-way routing, parallelize claim verification, and replace the naive word-count heuristic with adaptive retrieval.

### Issues Fixed
| # | Issue | Severity |
|---|-------|----------|
| 7 | Silent claim extraction failure → perfect grounding score | HIGH |
| 8 | Binary critic verdict instead of 4-way routing | HIGH |
| 12 | Word count as query complexity heuristic | HIGH |
| 13 | Hardcoded k=5 with no adaptive top-k | MEDIUM |
| 14 | All claim verification in a single LLM call (batch mode) | MEDIUM |

---

#### 3A — Fix Claim Extraction Failure Handling

**Files affected:**
- `backend/agents/critic/agent.py` — Change `if not claims: return {"grounding_score": 1.0, ...}` to return `0.0` and `"is_hallucinated": True, "reasoning": "No claims could be extracted"`. Add a new field `verification_mode: Literal["claims_verified", "no_claims", "extraction_failed"]`.
- `backend/graph/edges.py` — Handle `verification_mode="no_claims"` as a special routing path that short-circuits to output with degradation flag.

**Architecture changes:**
- `verify_grounding()` return dict gains `verification_mode` field.
- `should_heal()` uses `verification_mode` to distinguish "verified clean" from "nothing to verify."

**Database migrations:** None.
**API changes:** Response metadata includes `verification_mode` field.
**Breaking changes:** Any code consuming the old `grounding_score` default of 1.0 will see 0.0 instead. This is the correct behavior but may surface incorrectly calibrated thresholds.
**Rollback strategy:** Revert `agent.py` to return `grounding_score=1.0` on empty claims.
**Validation:** Sending an empty answer through the critic returns `grounding_score=0.0`, `verification_mode="no_claims"`, `is_hallucinated=True`.
**Test plan:** 3 unit tests — (1) empty answer → score=0.0, (2) model refusal → score=0.0, (3) valid answer + claims → score as expected.

**Estimated complexity:** 2 / 10
**Estimated risk:** 3 / 10

---

#### 3B — 4-Way Critic Routing + Parallel Claim Verification

**Files affected:**
- `backend/agents/critic/agent.py` — Expand verdict tracking to 4 categories: `FULLY_SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`. Return counts for all four.
- `backend/agents/critic/grounding_verifier.py` — Change `verify_claims_batch()` to fire parallel per-claim LLM calls using `asyncio.gather()` with a semaphore (concurrency limit=5). Each call returns a single-claim verdict to avoid context window overwhelm.
- `backend/graph/edges.py` — Replace binary return with 4-branch routing:
  - `FULLY_SUPPORTED` → output (no healing needed)
  - `PARTIALLY_SUPPORTED` → healing with `target="expansion"` + query rewrite
  - `UNSUPPORTED` → healing with `target="source_reconciliation"` + different rewrite strategy
  - `CONTRADICTED` → healing with `target="contradiction_resolution"` + source replacement
- `backend/agents/healer/query_rewriter.py` — Accept `healing_target` parameter that changes the rewrite prompt/strategy.

**Architecture changes:**
- Critic produces a structured verdict with 4-category breakdown per claim and aggregated.
- Healing node receives a `healing_target` that selects different rewrite strategies.
- Parallel claim verification with semaphore-controlled concurrency.

**Database migrations:** None. (Existing `hallucination_events` table schema may need `verdict_distribution` column added — deferred to Phase 6.)
**API changes:** Response metadata includes `verdict_distribution: {supported: N, partial: N, unsupported: N, contradicted: N}`.
**Breaking changes:** Any downstream code consuming `is_hallucinated: bool` will see a richer structure. Backward-compatible if `is_hallucinated` is preserved as `contradicted_count > 0`.
**Rollback strategy:** Revert `edges.py` to binary routing. Revert verifier to batch mode.
**Validation:** A fully-supported answer routes to output. A partially-supported answer routes to healing with target="expansion". A contradicted answer routes to healing with target="contradiction_resolution".
**Test plan:** 5 unit tests — (1) 4-verdict routing each triggers correct healing path, (2) parallel verification returns correct per-claim verdicts, (3) semaphore limits concurrency to 5, (4) one LLM failure doesn't lose other claim results, (5) healing node uses target to select rewrite strategy.

**Estimated complexity:** 6 / 10
**Estimated risk:** 5 / 10

---

#### 3C — Adaptive Retrieval (Replace Word Count Heuristic + Static k)

**Files affected:**
- `backend/graph/nodes.py` — Replace `word_count <= 10` heuristic with a non-blocking complexity classifier. Options: (a) `asyncio.to_thread()` call to a fast embedding + distance-to-centroid classifier, (b) small DistilBERT model loaded once and cached, (c) prompt-based LLM classification if latency < 500ms is acceptable.
- Implement `adaptive_k(complexity_score)` function:
  - Simple (score < 0.3): k=3
  - Medium (0.3-0.7): k=5
  - Complex (> 0.7): k=10
  - Multi-hop (> 0.9): k=20
- `backend/graph/state.py` — Add `complexity_score: float = 0.0` and `target_k: int = 5` fields.
- `backend/storage/retriever.py` — Accept `k` parameter from state instead of hardcoded default.

**Architecture changes:**
- Query complexity becomes a first-class computed property in the pipeline.
- Retriever receives dynamic `k` based on complexity.
- `target_k` is passed through the graph state.

**Database migrations:** None.
**API changes:** Response metadata includes `complexity: float` and `retrieved_count: int`.
**Breaking changes:** None. Existing k=5 behavior becomes the default for medium-complexity queries.
**Rollback strategy:** Revert `nodes.py` to `word_count <= 10` heuristic.
**Validation:** A 5-word query classified as complex ("GDPR Article 17 extraterritorial scope") returns k=10+. A complex query classified as simple returns k=3.
**Test plan:** 4 unit tests — (1) complexity classifier returns float 0-1, (2) adaptive_k maps scores to correct k values, (3) retriever uses dynamic k from state, (4) word count no longer influences routing.

**Estimated complexity:** 5 / 10
**Estimated risk:** 4 / 10

---

### Phase 3 Summary

| Metric | Value |
|--------|-------|
| Files changed | 8-10 |
| DB migrations | 0 (schema changes deferred) |
| API changes | Richer verdict metadata in responses |
| Breaking changes | `is_hallucinated` behavior unchanged; `grounding_score` for empty claims changes from 1.0 → 0.0 |
| Total complexity | 7 / 10 |
| Total risk | 5 / 10 |
| Estimated effort | 5-7 days |

---

---

## Phase 4: Resilience & Observability

### Objective
Add PostgresCheckpointer for state persistence across failures, implement SSE streaming so users see progress, and replace homegrown telemetry with real OpenTelemetry + LangSmith.

### Issues Fixed
| # | Issue | Severity |
|---|-------|----------|
| 9 | No PostgresCheckpointer on graph compilation | HIGH |
| 15 | No OpenTelemetry — homegrown telemetry to Postgres | MEDIUM |
| 20 | No streaming API — all responses buffered | MEDIUM |
| 17 | Unbounded state size | MEDIUM |

---

#### 4A — PostgresCheckpointer for Graph Resilience

**Files affected:**
- `backend/graph/workflow.py` — Add `import PostgresCheckpointer from langgraph.checkpoint.postgres`. Modify `create_rag_graph()` to accept `checkpointer` parameter: `return workflow.compile(checkpointer=checkpointer)`.
- `backend/api/main.py` — Initialize `PostgresCheckpointer` in lifespan with async Postgres connection. Store in `app.state.checkpointer`. Pass to graph compilation.
- `backend/core/config.py` — Add `LANGGRAPH_CHECKPOINT_URI` setting pointing to Postgres.

**Architecture changes:**
- LangGraph workflow compiles with a Postgres-based checkpointer.
- Mid-pipeline failures can resume from the last checkpoint.
- Checkpointer uses the same Postgres connection pool (separate table namespace).

**Database migrations:** Alembic migration adds `checkpoints` and `checkpoint_blobs` tables (via `PostgresCheckpointer`'s built-in DDL).
**API changes:** None. Checkpointing is transparent to API consumers.
**Breaking changes:** None.
**Rollback strategy:** Remove `checkpointer=` argument from `workflow.compile()`.
**Validation:** Inject a simulated failure mid-pipeline, verify the next request can resume from checkpoint.
**Test plan:** 2 integration tests — (1) graph with checkpointer stores state in Postgres, (2) resume-from-checkpointer returns correct partial state.

**Estimated complexity:** 4 / 10
**Estimated risk:** 3 / 10

---

#### 4B — Server-Sent Events Streaming

**Files affected:**
- `backend/api/routers/query.py` — Add `GET /v1/query/stream` endpoint returning `StreamingResponse`. Emit typed SSE events:
  - `event: status` — `{"phase": "intake|planning|retrieval|generation|critic|healing|evaluation|output"}`
  - `event: chunk` — `{"content": "...", "score": 0.95, "source": "doc.pdf"}`
  - `event: claims` — `{"count": 5, "supported": 4, "contradicted": 0}`
  - `event: token` — `{"text": "generated", "index": 42}` (streaming generation tokens)
  - `event: error` — `{"message": "...", "phase": "retrieval"}`
  - `event: complete` — `{"answer": "...", "metrics": {...}}`
- `backend/graph/nodes.py` — Accept optional callback function to emit streaming events during execution.
- `backend/graph/workflow.py` — Pass streaming callback through graph execution context.
- `backend/graph/runner.py` — Wire streaming callback from HTTP request to graph execution.

**Architecture changes:**
- Streaming callback pattern added to graph nodes. Each node emits events as it executes.
- `StreamingResponse` with `text/event-stream` content type.
- Frontend can connect to `/v1/query/stream` with `EventSource`.

**Database migrations:** None.
**API changes:** New `GET /v1/query/stream` endpoint. Existing `POST /v1/query` remains unchanged.
**Breaking changes:** None. Backward-compatible with existing buffered endpoint.
**Rollback strategy:** Remove streaming endpoint. Revert to buffered-only responses.
**Validation:** SSE stream emits correct events in order: intake → planning → retrieval → generation → critic → (healing loop) → evaluation → output.
**Test plan:** 2 integration tests — (1) SSE stream produces expected event sequence, (2) SSE timeout handling. 1 E2E test with frontend EventSource connection.

**Estimated complexity:** 6 / 10
**Estimated risk:** 4 / 10

---

#### 4C — OpenTelemetry + LangSmith Integration

**Files affected:**
- `backend/core/telemetry.py` — Replace placeholder `setup_telemetry()` with real OTel SDK initialization:
  - Configure `TracerProvider` with OTLP exporter to Tempo/Honeycomb/console.
  - Configure `BatchSpanProcessor`.
  - Set up `FastAPIInstrumentor` for automatic HTTP middleware spans.
  - Configure `LangSmithInstrumentor` if available, or manual LangSmith SDK client.
- `backend/core/telemetry_collector.py` — Deprecate custom `log_trace()` and `log_metrics()` functions. Replace with real OTel spans:
  - `tracer.start_as_current_span("rag.graph.phase", attributes={"phase": ..., "agent": ...})`.
  - Record `latency_ms` as span duration (automatic via context manager).
  - Record `tokens_used` as span attribute.
  - Add events: `span.add_event("claims_verified", {"supported": N, ...})`.
- `backend/graph/nodes.py` — Add OTel span context managers in each node function. Use `tracer.start_as_current_span(f"rag.node.{node_name}")`.
- `backend/graph/runner.py` — Create root span for full graph execution, set parent from incoming request trace context.
- `backend/api/main.py` — Ensure `FastAPIInstrumentor.instrument_app(app)` is called. Set `OTEL_SERVICE_NAME` env var.
- `backend/core/config.py` — Add OTel settings: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.
- `pyproject.toml` — Add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`, `langsmith`.

**Architecture changes:**
- Full W3C trace context propagation: incoming HTTP request → FastAPI middleware → LangGraph nodes → LLM calls → LangSmith.
- Distributed traces visible in Grafana Tempo / Datadog APM.
- LangSmith traces for every LLM call.
- Custom `TelemetryCollector` class either removed or reduced to a lightweight wrapper around OTel spans.
- Trace-to-logs correlation via `trace_id` in log records.

**Database migrations:** None. The `execution_traces` and `evaluation_metrics` tables become secondary to OTel. They can be deprecated in a future phase.
**API changes:** Response headers include `X-Trace-ID` for user-facing trace lookup. HTTP response times improve (no DB write per trace event).
**Breaking changes:** Any system reading from `execution_traces` table directly will see reduced data volume (traces go to OTel instead). Mitigation: dual-write during transition.
**Rollback strategy:** Revert `telemetry.py` to placeholder. Restore custom collector.
**Validation:** 10 requests → 10 traces appear in Tempo/Grafana. Each trace has spans for every graph node. LangSmith shows LLM call traces with input/output.
**Test plan:** 2 integration tests — (1) trace context propagates from HTTP to graph, (2) span attributes include correct phase/agent names. Manual validation with OTel console exporter.

**Estimated complexity:** 5 / 10
**Estimated risk:** 4 / 10

---

#### 4D — Bounded State Lists

**Files affected:**
- `backend/graph/state.py` — Replace unbounded `List[RetrievedChunk]` with `BoundedList(max_size=20)`. Replace `Annotated[List[str], operator.add]` for `error_log` with `BoundedList(max_size=10)`. Implement `BoundedList` as a Pydantic-compatible class that evicts oldest entries on overflow.
- `backend/graph/nodes.py` — In `healing_node`, reset `retrieved_chunks` to `[]` (already done). Add explicit trimming of `error_log` after each healing cycle.

**Architecture changes:**
- State object has explicit size caps.
- Old chunks/errors are evicted rather than accumulated.
- Prevents context window overflow in long healing loops.

**Database migrations:** None.
**API changes:** Response metadata reflects trimmed state (max 20 chunks returned).
**Breaking changes:** Downstream consumers that expect unlimited chunks will see fewer. Impact: zero (no such consumers exist).
**Rollback strategy:** Revert `BoundedList` to plain `List`.
**Validation:** State with 25 chunks trims to 20. Error log with 15 entries trims to 10.
**Test plan:** 3 unit tests — (1) append to bounded list evicts oldest, (2) healing_node resets chunks, (3) error_log trimming after healing.

**Estimated complexity:** 2 / 10
**Estimated risk:** 1 / 10

---

### Phase 4 Summary

| Metric | Value |
|--------|-------|
| Files changed | 12-15 |
| DB migrations | 1 (checkpoint tables) |
| API changes | New SSE streaming endpoint |
| Breaking changes | Telemetry shifts from Postgres to OTel (dual-write during transition) |
| Total complexity | 8 / 10 |
| Total risk | 6 / 10 |
| Estimated effort | 7-10 days |

---

---

## Phase 5: Evaluation & Testing Infrastructure

### Objective
Replace the custom composite score with real RAGAS metrics, move evaluation offline, and build the test pyramid from unit to E2E. After this phase, quality is measurable via industry-standard metrics and all code changes have safety nets.

### Issues Fixed
| # | Issue | Severity |
|---|-------|----------|
| 10 | Evaluation runs synchronously inline on every query | HIGH |
| 11 | No actual RAGAS integration — custom undefined composite score | HIGH |
| 21 | Only 2 smoke tests exist — catastrophic test gap | HIGH |
| 25 | No Alembic migrations directory | MEDIUM |

---

#### 5A — Offline RAGAS Evaluation Pipeline

**Files affected:**
- `backend/agents/evaluation/agent.py` — Complete rewrite:
  - Remove synchronous `evaluate_response()` from graph serving path.
  - Create async function `evaluate_offline(query, answer, contexts, ground_truth)`.
  - Integrate `ragas` library: compute `faithfulness`, `answer_relevance`, `context_precision`, `context_recall`.
  - Store per-dimension scores, not just composite.
  - Add `async with AsyncSessionLocal() as session: ...` to persist in `evaluation_metrics` table.
- `backend/graph/workflow.py` — Remove `evaluation_node` from serving graph. Replace with an async background task that fires after response is returned.
- `backend/graph/nodes.py` — Keep `evaluation_node` but change it to only queue an offline evaluation task (push to Redis queue). Return immediately.
- `backend/core/telemetry_collector.py` — Add RAGAS metrics to Postgres + OTel span for offline evaluation.
- `backend/evaluation/benchmark.py` — Refactor to load evaluation dataset, run RAGAS, and produce HTML/JSON report. Add comparison against previous run.
- `scripts/run_eval.py` — Create entry point for CLI evaluation run.

**New files:**
- `backend/evaluation/eval_dataset.jsonl` — 200 QA pairs with ground truth contexts.
- `backend/evaluation/runner.py` — Orchestrator that loads dataset → runs queries → computes RAGAS → produces report.

**Architecture changes:**
- Evaluation removed from serving critical path. P99 latency drops by 3-8s.
- RAGAS computed offline via Celery/Redis task or CLI script.
- Per-dimension scores stored separately for granular analysis.
- Evaluation can be run on-demand or as a CI gate.

**Database migrations:** Alembic migration adds columns to `evaluation_metrics` for each RAGAS dimension (`faithfulness`, `answer_relevance`, `context_precision`, `context_recall`) if not already present.
**API changes:** Response no longer waits for evaluation. `POST /v1/query` returns immediately after output_node. A separate `GET /v1/query/{id}/eval` endpoint provides evaluation results.
**Breaking changes:** Response latency drops significantly. Any code blocking on evaluation completion in the response must be updated.
**Rollback strategy:** Restore `evaluation_node` to the serving graph.
**Validation:** Running `scripts/run_eval.py` against 20 test queries produces faithfullness, answer_relevance, context_precision, context_recall scores in a structured report.
**Test plan:** 3 unit tests — (1) RAGAS faithfulness score < 0.5 for hallucinated answer, (2) context_precision = 0.0 for irrelevant context, (3) offline queue fires correctly. 1 integration test — evaluation produces all 4 dimension scores.

**Estimated complexity:** 6 / 10
**Estimated risk:** 4 / 10

---

#### 5B — Test Infrastructure (Test Pyramid)

**Files affected:**
- `backend/tests/` — Full restructure:
  - `backend/tests/unit/` — Agent unit tests with mocked dependencies:
    - `test_critic_agent.py` — Claim extraction, grounding verification, 4-way routing.
    - `test_hybrid_retriever.py` — RRF fusion, tenant isolation, adaptive k.
    - `test_generation_agent.py` — Answer generation with mocked LLM.
    - `test_query_cache.py` — Cache hit/miss, tenant isolation.
    - `test_session_memory.py` — Add/retrieve/clear with mocked Redis.
    - `test_healer.py` — Query rewrite strategies.
    - `test_evaluation.py` — RAGAS score computation.
    - `test_chunker.py` — Deterministic chunk IDs, chunk boundaries.
    - `test_reranker.py` — Cross-encoder reranking, fallback behavior.
    - `test_nodes.py` — Each graph node function with mocked state.
    - `test_edges.py` — 4-way routing, max retries, healing trigger.
    - `test_state.py` — Bounded list eviction, state initialization.
    - `test_security.py` — Prompt injection detection, auth token validation.
  - `backend/tests/integration/` — Integration tests with real Docker services:
    - `test_chroma_integration.py` — Multi-tenant ChromaDB operations.
    - `test_postgres_integration.py` — Connection pool, concurrent writes.
    - `test_redis_integration.py` — Async Redis session operations.
    - `test_retrieval_integration.py` — Full hybrid retrieval against real Chroma+BM25.
    - `test_full_pipeline.py` — End-to-end LangGraph with real dependencies.
  - `backend/tests/e2e/` — End-to-end tests:
    - `test_query_e2e.py` — Full HTTP request → response cycle.
    - `test_ingest_e2e.py` — Upload document → verify it appears in retrieval.
    - `test_healing_e2e.py` — Query that triggers healing loop, verify self-correction.
- `conftest.py` — Shared fixtures, mocked agents, test database setup.
- `pytest.ini` or `pyproject.toml` — Pytest configuration with markers: `unit`, `integration`, `e2e`, `slow`.

**Architecture changes:**
- Test pyramid with clearly separated layers.
- Mock fixtures available for all external dependencies (ChromaDB, Redis, Postgres, LLM).
- Integration tests require Docker Compose services (via `pytest-docker` or Make targets).
- CI runs unit tests (<30s), integration tests (<2min), E2E tests (<10min, nightly).

**Database migrations:** Test database setup via Alembic (separate test DB or in-memory SQLite for unit tests).
**API changes:** None.
**Breaking changes:** None.
**Rollback strategy:** Test infrastructure is additive, not destructive. Old `test_api_smoke.py` remains.
**Validation:** `pytest backend/tests/unit/` passes with 100% coverage of mocked agent paths. `pytest backend/tests/integration/` passes with Docker Compose services running.
**Test plan:** Target: 50+ unit tests, 10+ integration tests, 3+ E2E tests. Coverage threshold: 80% for agent code.

**Estimated complexity:** 7 / 10
**Estimated risk:** 3 / 10

---

### Phase 5 Summary

| Metric | Value |
|--------|-------|
| Files changed | 20-25 (mostly test files) |
| DB migrations | 1 (RAGAS metric columns) |
| API changes | New `GET /v1/query/{id}/eval` endpoint |
| Breaking changes | Response no longer includes inline evaluation metrics |
| Total complexity | 8 / 10 |
| Total risk | 4 / 10 |
| Estimated effort | 7-10 days |

---

---

## Phase 6: Security Hardening & Operational Readiness

### Objective
Harden for production: RS256 JWT, RBAC, audit logging, prompt injection at the LLM level, load shedding, deployment hardening, and API versioning.

### Issues Fixed
| # | Issue | Severity |
|---|-------|----------|
| 16 | Graph context prepended as string to first chunk | MEDIUM |
| 19 | ChromaDB allow_reset=True in production | HIGH |
| 22 | No API versioning | LOW |
| 23 | No load shedding or request queuing | MEDIUM |
| 24 | Prompt injection detection uses static regex blocklist | MEDIUM |
| 25 | No Alembic migrations directory | MEDIUM |
| (18) | HS256 JWT → RS256 (continuing from Phase 2 prep) | MEDIUM |

---

#### 6A — Structured Graph Results + ChromaDB Security

**Files affected:**
- `backend/storage/retriever.py` — Change graph context handling: instead of `final_results[0]["content"] += graph_context`, create separate graph result entries with `source: "knowledge_graph"` metadata. Add them to `fused_scores` as independently scored items.
- `backend/storage/vector/chroma.py` — Change `allow_reset=True` to `allow_reset=False` in the `ChromaSettings(allow_reset=False)`. Add environment-specific override for dev environments (not via settings hardcode — use `settings.CHROMA_ALLOW_RESET` env var that defaults to `False`).
- `backend/core/config.py` — Add `CHROMA_ALLOW_RESET: bool = False` setting. Add `CHROMA_AUTH_HEADER` setting for future token-based ChromaDB auth.

**Architecture changes:**
- Graph results become first-class, independently-sourced entries in the fused result list.
- ChromaDB `reset()` API is disabled in production.
- Environment-specific override via `CHROMA_ALLOW_RESET=true` env var for dev.

**Database migrations:** None.
**API changes:** None (graph results structure changes are internal).
**Breaking changes:** ChromaDB reset capability disabled — any scripts relying on `reset()` must use `CHROMA_ALLOW_RESET=true` env var.
**Rollback strategy:** Revert to `allow_reset=True` and string-prepend graph context.
**Validation:** Graph results appear as separate entries with `source: "knowledge_graph"`. ChromaDB HTTP `reset()` returns 403.
**Test plan:** 2 unit tests — (1) graph context as independent fused entries, (2) allow_reset=False blocks reset API.

**Estimated complexity:** 2 / 10
**Estimated risk:** 2 / 10

---

#### 6B — JWT Upgrade to RS256 + API Versioning

**Files affected:**
- `backend/core/security.py` — Replace `HS256` with `RS256`:
  - Generate RSA key pair on startup (development) or load from files (production).
  - `SECRET_KEY` becomes `PRIVATE_KEY_PATH` and `PUBLIC_KEY_PATH` settings.
  - `create_access_token()` signs with private key.
  - `decode_token()` (in auth router) verifies with public key.
  - Only the auth service holds the private key.
- `backend/core/config.py` — Add `JWT_ALGORITHM = "RS256"`, `RSA_PRIVATE_KEY_PATH`, `RSA_PUBLIC_KEY_PATH`.
- `backend/api/routers/auth.py` — Update `jwt.decode()` to use `public_key` from settings.
- `backend/api/main.py` — Add `prefix="/v1"` to all routers. Keep current routes working via redirect or dual-registration.

**Architecture changes:**
- Asymmetric JWT signing: auth server signs, other services verify with public key only.
- API routes versioned at `/v1/...`. Old routes redirect or return 301.

**Database migrations:** None.
**API changes:** Routes move from `/query` to `/v1/query`. Old paths redirect.
**Breaking changes:** All existing JWT tokens (HS256-signed) will be invalid after RS256 switch. All API clients must update their base URL to `/v1/...`.
**Rollback strategy:** Keep HS256 as fallback. Validate token against both HS256 and RS256 during transition.
**Validation:** RS256-signed token is verified by auth service. HS256-signed token is rejected after transition window.
**Test plan:** 3 unit tests — (1) RS256 sign + verify round trip, (2) HS256 token rejected after deadline, (3) /v1/ routes return 200, non-versioned routes return 301.

**Estimated complexity:** 4 / 10
**Estimated risk:** 5 / 10

---

#### 6C — Load Shedding + Request Queuing

**Files affected:**
- `backend/api/middleware/rate_limit.py` — Enhance rate limiter:
  - Add per-user burst limit distinct from sustained limit.
  - Implement token bucket algorithm (Redis-based) instead of fixed window.
  - Add concurrency limiter: max 5 concurrent graph executions per pod.
- `backend/api/routers/query.py` — Add `asyncio.Semaphore(concurrent_limit)` guard around graph execution. Return 429 with `Retry-After` header when limit reached.
- `backend/graph/runner.py` — Add timeout wrapper: `asyncio.wait_for(graph_execution, timeout=120)` to prevent runaway queries.
- `backend/core/config.py` — Add `MAX_CONCURRENT_QUERIES: int = 5`, `QUERY_TIMEOUT_SECONDS: int = 120`.

**Architecture changes:**
- Rate limiter moves from fixed-window to token-bucket algorithm.
- Concurrency semaphore prevents Ollama/LLM overload.
- Query timeout prevents resource leaks from stuck pipelines.

**Database migrations:** None.
**API changes:** `429 Too Many Requests` responses include `Retry-After` and `X-RateLimit-*` headers.
**Breaking changes:** None. Rate limiting is additive.
**Rollback strategy:** Remove semaphore guard, revert rate limiter to fixed-window.
**Validation:** 6 concurrent requests → 5 execute, 1 returns 429. Query that exceeds 120s returns 504.
**Test plan:** 2 integration tests — (1) concurrency limit enforced via semaphore, (2) rate limiter returns 429 with correct headers. 1 load test: 50 requests in 10s.

**Estimated complexity:** 4 / 10
**Estimated risk:** 3 / 10

---

#### 6D — Prompt Injection Defense Upgrade

**Files affected:**
- `backend/core/security.py` — Replace regex blocklist with LLM-as-judge pattern:
  - Add pre-query filter: fast embedding-based classifier for known injection patterns.
  - Add post-query filter: generation output scanned for system prompt leakage.
  - Add test harness for injection detection accuracy (benchmark).
  - Keep regex as first-pass filter (fast rejection), add classifier as second pass (accurate rejection).
- `backend/api/middleware/rate_limit.py` — Add injection-attempt-specific rate limit: 3 injection attempts per user per hour triggers 24-hour ban.

**Architecture changes:**
- Two-stage prompt injection detection: fast regex (low FP) → embedding classifier (high recall).
- Injection attempts are rate-limited independently of query rate limit.
- Benchmark suite for injection detection performance.

**Database migrations:** None.
**API changes:** 403 response for detected injection attempts includes `block_reason: "prompt_injection"`.
**Breaking changes:** None.
**Rollback strategy:** Remove classifier, keep regex-only filter.
**Validation:** 10 known injection patterns → 9+ detected. 100 legitimate queries → 0 flagged as injection.
**Test plan:** 3 unit tests — (1) known injection pattern blocked at regex level, (2) obfuscated injection blocked at classifier level, (3) legitimate query passes both stages.

**Estimated complexity:** 5 / 10
**Estimated risk:** 3 / 10

---

#### 6E — RBAC + Audit Logging

**Files affected:**
- `backend/storage/db/models.py` — Add `Role` enum and `User.role` column. Add `AuditLog` table with columns: `id`, `user_id`, `action`, `resource`, `details`, `ip_address`, `user_agent`, `timestamp`.
- `backend/api/routers/auth.py` — Add role-based decorators: `require_role(["admin", "editor"])`. Add `/auth/users` endpoints for admin user management.
- `backend/api/middleware/rate_limit.py` — Add audit logging middleware that logs every mutating API call to `AuditLog` table.
- `backend/core/logging.py` — Add audit logger that writes structured audit events.

**Architecture changes:**
- Role-based access control (RBAC) for API endpoints.
- Audit log for all mutating operations (ingest, delete, user management, config changes).
- Admin endpoints for user management.

**Database migrations:** Alembic migration: add `role` column to `users` table. Create `audit_logs` table.
**API changes:** New `GET /v1/admin/users`, `POST /v1/admin/users/{id}/role` endpoints. Existing endpoints check role for write operations.
**Breaking changes:** None for existing users. Admin endpoints require `admin` role.
**Rollback strategy:** Remove role checks from endpoints. Drop audit log table.
**Validation:** User with `viewer` role receives 403 on ingest endpoint. Admin user receives 200. Each ingest call creates an audit log entry.
**Test plan:** 3 integration tests — (1) viewer cannot ingest, (2) admin can ingest, (3) audit log entry created for each mutating operation.

**Estimated complexity:** 5 / 10
**Estimated risk:** 4 / 10

---

#### 6F — Deployment Hardening

**Files affected:**
- `docker-compose.yml` — Add `restart: unless-stopped` to all services. Add resource limits: `deploy.resources.limits.cpus`, `deploy.resources.limits.memory`. Add `healthcheck` to API service. Add `networks` for service isolation.
- `infra/k8s/api.yaml` — Add HPA resource limits. Add PodDisruptionBudget. Add readiness/liveness probes with proper initial delay. Add secrets for DB credentials.
- `infra/docker/Dockerfile.api` — Add non-root user. Add `--no-cache-dir` to pip installs. Add multi-stage build to reduce image size.
- `infra/monitoring/prometheus/prometheus.yml` (new) — Prometheus scrape config for API metrics.
- `infra/monitoring/grafana/dashboards/system_health.json` — Create dashboard showing request rate, error rate, P50/P95/P99 latency, memory/CPU per pod.

**Architecture changes:**
- Production Docker Compose setup with resource limits and health checks.
- K8s deployment with HPA, PDB, and secrets management.
- Prometheus metrics endpoint for API (`/metrics`) via OTel.
- Non-root container execution.

**Database migrations:** None.
**API changes:** New `/metrics` endpoint (Prometheus).
**Breaking changes:** Docker Compose dev environment changes (resource limits may cause OOM on low-resource machines). Mitigation: separate `docker-compose.dev.yml` and `docker-compose.prod.yml`.
**Rollback strategy:** Revert Docker Compose changes. Use previous K8s manifest.
**Validation:** `docker compose up` starts all services with healthchecks. K8s apply creates pods with correct resource limits.
**Test plan:** 1 smoke test — `docker compose up` and healthcheck passes. 1 K8s test — `kubectl apply -f infra/k8s/api.yaml` creates pods.

**Estimated complexity:** 5 / 10
**Estimated risk:** 4 / 10

---

### Phase 6 Summary

| Metric | Value |
|--------|-------|
| Files changed | 15-18 |
| DB migrations | 1 (role + audit_log) |
| API changes | `/v1/` prefix, admin endpoints, metrics endpoint, 429/403 responses |
| Breaking changes | JWT token invalidation (HS256→RS256), API prefix migration |
| Total complexity | 7 / 10 |
| Total risk | 7 / 10 |
| Estimated effort | 7-10 days |

---

---

## Complete Roadmap Overview

### Dependency Graph

```
Phase 1 (Isolation) ──┐
                       ├──→ Phase 3 (Critic + Retrieval)
Phase 2 (Infra) ──────┘         │
                                 ├──→ Phase 4 (Resilience + Observability)
Phase 3 ────────────────────────┘         │
                                           ├──→ Phase 5 (Evaluation + Tests)
Phase 4 ──────────────────────────────────┘         │
                                                     └──→ Phase 6 (Security + Production)
Phase 5 ────────────────────────────────────────────┘
```

### Delivery Timeline

| Phase | Objective | Duration | Risk | Dependencies |
|-------|-----------|----------|------|-------------|
| 1 | Data Isolation & Identifiers | 2-3 days | Low | None |
| 2 | PostgreSQL + DI + Async Redis | 5-7 days | Medium | Phase 1 |
| 3 | Critic + Adaptive Retrieval | 5-7 days | Medium | Phase 1, 2 |
| 4 | Checkpointing + Streaming + OTel | 7-10 days | Medium-High | Phase 2 |
| 5 | RAGAS + Test Infrastructure | 7-10 days | Medium | Phase 3 (for eval accuracy) |
| 6 | Security Hardening + Production | 7-10 days | High | Phase 2, 4, 5 |
| **Total** | | **33-47 days** | | |

### Key Dependencies Between Phases

1. **Phase 2 → Phase 4**: PostgresCheckpointer requires PostgreSQL from Phase 2. Async Redis from Phase 2 enables streaming event queue.
2. **Phase 1 → Phase 3**: Tenant isolation in retriever is needed before adaptive k changes to avoid multi-tenant cross-contamination.
3. **Phase 3 → Phase 5**: RAGAS evaluation depends on correct critic/retrieval behavior for accurate quality measurement.
4. **Phase 4 → Phase 6**: Streaming and observability infrastructure is needed before production deployment hardening.

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| PostgreSQL migration breaks existing data | Run migration script in dry-run mode first. Keep SQLite as fallback for 1 sprint. |
| DI refactoring introduces regression | Parallel legacy path during transition. Feature-flag new DI path. |
| RS256 key management complexity | Use environment-mounted key files on K8s. Document key rotation procedure. |
| RAGAS dependency conflicts | Pin ragas version. Isolate in separate evaluation service if needed. |
| Streaming API performance overhead | Profile SSE overhead vs buffered path. Default to buffered, opt-in to streaming. |

### Success Criteria

| Metric | Phase 0 (Current) | Phase 6 (Target) |
|--------|-------------------|------------------|
| Cross-tenant data leak risk | P0 (no isolation) | None |
| Chunk ID reliability | Breaks on every healing cycle | Deterministic, survives cycles |
| Concurrent request safety | SQLite deadlock | Postgres pool, no corruption |
| P99 latency | 25s+ (including eval) | <10s (streaming: first token <5s) |
| Critic accuracy | 0/0/0 quotes | All 4 verdicts tracked |
| Test count | 2 | 50+ unit, 10+ integration, 3+ E2E |
| Coverage | <5% | >80% agent code |
| Prompt injection detection | Regex blocklist | 2-stage (regex + classifier) |
| Auth model | HS256 symmetric | RS256 asymmetric |
| API versioning | None | `/v1/` prefix |
| Traceability | Custom Postgres table | OpenTelemetry + LangSmith |