# Implementation Master Plan — Optimized for Minimal Rework

## Self-Healing Multi-Agent RAG Platform

> **Source:** Code-verified `REMEDIATION_PLAN.md` (25 issues)  
> **Principle:** Every file is modified exactly once per logical concern group — no repeated edits to the same file across phases unless unavoidable.  
> **Constraint:** Do not implement anything yet — this is the execution specification only.

---

## Issue-to-Phase Mapping (Optimized for Minimal File Touches)

```
File                     | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total Touches
-------------------------|---------|---------|---------|---------|--------------
nodes.py                 |   x     |   x     |   x     |         | 3  ← unavoidable
workflow.py              |         |         |   x     |         | 1
state.py                 |         |   x     |         |         | 1
main.py                  |         |         |   x     |   x     | 2
session.py               |   x     |         |         |         | 1
security.py              |   x     |         |         |   x     | 2  ← JWT + injection
config.py                |   x     |         |         |   x     | 2  ← infra + security
chroma.py                |         |   x     |         |         | 1
retriever.py             |         |   x     |         |         | 1
reranker.py              |         |   x     |         |         | 1
bm25.py                  |         |   x     |         |         | 1
critic/agent.py          |         |   x     |         |         | 1
grounding_verifier.py    |         |   x     |         |         | 1
edges.py                 |         |   x     |         |         | 1
chunker.py               |         |   x     |         |         | 1
pipeline.py              |         |   x     |         |         | 1
evaluation/agent.py      |         |         |   x     |         | 1
telemetry.py             |         |         |   x     |         | 1
telemetry_collector.py   |         |         |   x     |         | 1
query.py (router)        |         |         |   x     |         | 1
runner.py                |         |         |   x     |         | 1
rate_limit.py            |         |         |         |   x     | 1
logging.py               |         |         |         |   x     | 1
models.py                |         |         |         |   x     | 1
auth.py (router)         |         |         |         |   x     | 1
Alembic init             |   x     |         |         |         | 1
Test files               |         |         |         |   x     | 1
Docker/K8s files         |         |         |         |   x     | 1
```

**Optimization result:** Every file is touched at most 2 times except `nodes.py` (3 times, unavoidable due to dependency ordering). Original naive plan would have touched `nodes.py` 6+ times.

---

## Per-Issue Detail Specification

### Legend
| Field | Description |
|-------|-------------|
| **Dependencies** | Issues that must be resolved before this one |
| **Prerequisites** | Code changes that must be merged first |
| **Files Affected** | Exact files with line ranges |
| **Complexity** | 1-10 (code complexity, not time) |
| **Risk** | 1-10 (probability of breaking something) |
| **Breaking Changes** | API/DB/behavior changes that require coordination |
| **Migration** | Data or config migration needed |
| **Tests Required** | Minimum test count and type |

---

#### Issue #1 — Sync Redis Blocking Async Event Loop
| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/memory/session.py:11-29` (rewrite constructor + all methods), `backend/graph/nodes.py:43,218-219` (add `await`), `backend/core/config.py` (add `REDIS_POOL_SIZE`) |
| **Complexity** | 3/10 |
| **Risk** | 4/10 — Missed `await` creates silent bugs (no error, just wrong result) |
| **Breaking Changes** | `SessionMemory` method signatures remain the same but now return coroutines. Any sync caller breaks. |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) async session writes under concurrency, (2) history retrieval returns correct messages, (3) TTL is set. 1 load: 50 concurrent writes P99 < 200ms. |

---

#### Issue #3 — SQLite Fallback Corrupts Under Concurrency
| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Dependencies** | None |
| **Prerequisites** | Docker Compose PostgreSQL service must be running |
| **Files Affected** | `backend/storage/db/session.py:12-15,34-42` (remove SQLite fallback, configure pool), `backend/core/config.py` (DATABASE_URL default to Postgres, add pool settings), `pyproject.toml` (add `asyncpg`, `alembic`, `psycopg2-binary`) |
| **Complexity** | 3/10 |
| **Risk** | 6/10 — Developers without Postgres running locally cannot start the app |
| **Breaking Changes** | SQLite-based local dev stops working. All dev environments must run `docker compose up -d postgres`. |
| **Migration** | Data migration: `scripts/migrate_sqlite_to_postgres.py` copies `nexus_core.db` → Postgres. Run once before deploy. |
| **Tests Required** | 2 integration: (1) 10 concurrent DB writes no `database is locked`, (2) pool health under load. |

---

#### Issue #6 — Chunk IDs Missing (Empty String IDs)
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/ingestion/chunker.py` (return deterministic SHA-256 IDs), `backend/ingestion/pipeline.py` (propagate IDs through pipeline), `backend/storage/retriever.py:78` (use ingested ID instead of `""`), `backend/graph/nodes.py:114` (remove `str(uuid.uuid4())`) |
| **Complexity** | 2/10 |
| **Risk** | 2/10 |
| **Breaking Changes** | Chunk IDs change from UUID4 to SHA-256 hashes. Systems referencing old IDs (none exist) break. |
| **Migration** | Re-index all documents in ChromaDB to get new IDs. Old chunks with UUID4 IDs become orphaned. |
| **Tests Required** | 3 unit: (1) same content → same ID, (2) different content → different ID, (3) retriever returns IDs from chunker, not generated at retrieval time. |

---

#### Issue #7 — HS256 JWT with Hardcoded Fallback Secret
| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/core/security.py:8` (remove fallback, fail if SECRET_KEY not set), `backend/core/config.py` (add `SECRET_KEY` field without default, add `JWT_ALGORITHM`) |
| **Complexity** | 1/10 |
| **Risk** | 5/10 — If SECRET_KEY is not set in production env, the app refuses to start. This is intentional but requires deployment config change. |
| **Breaking Changes** | Existing .env files must add `SECRET_KEY`. JWT tokens signed with old key become invalid on restart. |
| **Migration** | None. Generate new SECRET_KEY for each environment. |
| **Tests Required** | 2 unit: (1) missing SECRET_KEY raises error at startup, (2) token sign+verify works with env-provided key. |

---

#### Issue #20 — No Alembic Migrations Directory
| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Dependencies** | #3 (PostgreSQL) |
| **Prerequisites** | Postgres running |
| **Files Affected** | New directory `backend/alembic/`, new file `backend/alembic.ini`, new file `backend/alembic/env.py`, new version `001_initial_schema.py` |
| **Complexity** | 2/10 |
| **Risk** | 3/10 — First-time Alembic setup may miss autogenerate detection of some models |
| **Breaking Changes** | None |
| **Migration** | `alembic upgrade head` creates all tables from current models. This replaces `init_db()` which always ran `Base.metadata.create_all`. |
| **Tests Required** | 1 integration: alembic upgrade + downgrade produces correct schema. |

---

#### Issue #25 — No DB Connection Pooling Configuration
| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Dependencies** | #3 (PostgreSQL) |
| **Prerequisites** | #3 merged |
| **Files Affected** | `backend/storage/db/session.py:11` (add pool_size, max_overflow, pool_pre_ping to `create_async_engine`), `backend/core/config.py` (add pool settings) |
| **Complexity** | 1/10 |
| **Risk** | 1/10 |
| **Breaking Changes** | None |
| **Migration** | None |
| **Tests Required** | 1 integration: pool exhaustion under 20 concurrent requests returns 503, not crash. |

---

#### Issue #4 — Empty Claims → Perfect Grounding Score
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/agents/critic/agent.py:24-25` (change return values + add `verification_mode` field) |
| **Complexity** | 2/10 |
| **Risk** | 3/10 — Downstream code that assumes `grounding_score` is always ≥0.5 may break. |
| **Breaking Changes** | `grounding_score` drops from 1.0 → 0.0 for empty answers. Any threshold-based routing breaks if it assumes 1.0 was correct. |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) empty answer → score=0.0, is_hallucinated=True, verification_mode="no_claims". (2) model refusal → same. (3) valid claims → verification_mode="claims_verified". |

---

#### Issue #5 — Binary Critic Verdict Instead of 4-Way Routing
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | #4 (verification_mode field) |
| **Prerequisites** | #4 merged |
| **Files Affected** | `backend/agents/critic/agent.py:31-32` (expand to 4-category tracking), `backend/graph/edges.py` (replace binary with 4-branch routing), `backend/agents/healer/query_rewriter.py` (accept `healing_target` parameter) |
| **Complexity** | 6/10 |
| **Risk** | 5/10 — New routing paths are exercised only on healing cycles, which are rare. Bugs may not surface until production. |
| **Breaking Changes** | `edges.py` routing logic changes. Old edge functions that expected `bool` now receive 4-category verdict. |
| **Migration** | None |
| **Tests Required** | 5 unit: (1) FULLY_SUPPORTED → output, (2) PARTIALLY_SUPPORTED → healing with target="expansion", (3) UNSUPPORTED → healing with target="source_reconciliation", (4) CONTRADICTED → healing with target="contradiction_resolution", (5) healer uses target to select rewrite strategy. |

---

#### Issue #10 — Batch Claim Verification in Single LLM Call
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None (can be done independently) |
| **Prerequisites** | None |
| **Files Affected** | `backend/agents/critic/grounding_verifier.py` (add `asyncio.gather` with semaphore=5, change `verify_claims_batch` to parallel per-claim calls) |
| **Complexity** | 5/10 |
| **Risk** | 4/10 — Rate limiting from Ollama may cause throttling with 5 concurrent LLM calls. |
| **Breaking Changes** | None (method signature unchanged) |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) parallel calls return correct per-claim verdicts, (2) semaphore limits concurrency to 5, (3) one LLM failure doesn't lose other claim results. |

---

#### Issue #11 — Word Count as Query Complexity Heuristic
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/graph/nodes.py:76-77` (replace word count check with complexity classifier), `backend/graph/state.py` (add `complexity_score` and `target_k` fields) |
| **Complexity** | 5/10 |
| **Risk** | 4/10 — Classifier adds latency. If it calls LLM, adds 500ms-2s. |
| **Breaking Changes** | None (routing output may change for queries that were previously misclassified) |
| **Migration** | None |
| **Tests Required** | 4 unit: (1) complexity classifier returns float 0-1, (2) adaptive_k maps scores to correct k, (3) retriever uses dynamic k, (4) word count no longer influences routing. |

---

#### Issue #12 — Hardcoded k=5 with No Adaptive Top-K
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | #11 (complexity_score) |
| **Prerequisites** | #11 merged |
| **Files Affected** | `backend/graph/nodes.py:101,107` (use `target_k` from state instead of hardcoded 5), `backend/storage/retriever.py` (accept `k` parameter), `backend/storage/bm25.py` (accept `k` parameter) |
| **Complexity** | 2/10 |
| **Risk** | 2/10 |
| **Breaking Changes** | None |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) k=3 for simple query, (2) k=10 for complex query, (3) k=20 for multi-hop query. |

---

#### Issue #12B — Re-embedding Entire Corpus on Startup
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/ingestion/pipeline.py` (add document registry check, add `is_indexed` flag), New file `backend/storage/document_registry.py` (SQLite or Postgres table tracking which documents are indexed), `backend/api/main.py` lifespan (skip re-index on startup if registry says indexed) |
| **Complexity** | 5/10 |
| **Risk** | 3/10 — Registry could become out of sync with actual ChromaDB state. |
| **Breaking Changes** | Startup time drops from 5-10 min to <1s. Any code depending on "all documents re-indexed on boot" breaks. |
| **Migration** | Run one-time full re-index to populate the registry, then incremental from there. |
| **Tests Required** | 3 unit: (1) new document gets indexed, (2) already-indexed document skipped, (3) registry sync check passes. |

---

#### Issue #15 — Graph Context Prepended as String to First Chunk
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/storage/retriever.py:110-112` (create separate graph result dict instead of string concatenation) |
| **Complexity** | 2/10 |
| **Risk** | 2/10 |
| **Breaking Changes** | Graph results change from string-appended to structured dicts with `source: "knowledge_graph"`. Downstream code assuming graph context is inside `chunks[0]["content"]` breaks. |
| **Migration** | None |
| **Tests Required** | 2 unit: (1) graph results appear as independent entries, (2) entries have correct `source` metadata. |

---

#### Issue #16 — Unbounded State Size
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/graph/state.py` (implement `BoundedList` class, replace `List[RetrievedChunk]` with `BoundedList(max_size=20)`, replace `Annotated[List[str], operator.add]` for `error_log` with `BoundedList(max_size=10)`) |
| **Complexity** | 2/10 |
| **Risk** | 1/10 |
| **Breaking Changes** | None (state consumers never relied on unbounded lists) |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) append to bounded list evicts oldest, (2) error_log trims at 10, (3) chunks list trims at 20. |

---

#### Issue #17 — ChromaDB allow_reset=True in Production
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/storage/vector/chroma.py:27` (change to `allow_reset=False`), `backend/core/config.py` (add `CHROMA_ALLOW_RESET: bool = False` setting with env var override) |
| **Complexity** | 1/10 |
| **Risk** | 1/10 |
| **Breaking Changes** | ChromaDB `reset()` API disabled by default. Dev environments set `CHROMA_ALLOW_RESET=true`. |
| **Migration** | None |
| **Tests Required** | 1 unit: allow_reset=False blocks reset API. |

---

#### Issue #17B — Reranker Silent Fallback on Load Failure
| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/storage/reranker.py:43` (add metric emission on fallback, add health check method) |
| **Complexity** | 1/10 |
| **Risk** | 1/10 |
| **Breaking Changes** | None |
| **Migration** | None |
| **Tests Required** | 2 unit: (1) fallback emits metric, (2) health check returns correct status. |

---

#### Issue #2 — Module-Level Global Singleton Agents
| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Dependencies** | #1 (async Redis — needed for DI container), #3 (PostgreSQL — needed for session DI) |
| **Prerequisites** | #1, #3 merged and tested |
| **Files Affected** | `backend/graph/nodes.py:22-32` (remove 11 singletons, create `create_graph_nodes(deps)` factory), `backend/graph/workflow.py` (accept `deps` parameter, remove module-level `rag_graph`), `backend/api/main.py` (create DI container in lifespan, wire graph factory), `backend/api/routers/query.py` (use dependency-injected graph from `app.state`), `backend/graph/runner.py` (accept injected graph at call time) |
| **Complexity** | 7/10 — Largest single refactor. Requires understanding all 11 dependency lifecycles. |
| **Risk** | 7/10 — Every graph node and every agent is rewired. High regression probability. Tests are essential before this phase. |
| **Breaking Changes** | `import rag_graph from backend.graph.workflow` breaks. All callers must use DI. |
| **Migration** | None. Old singleton import path becomes a `DeprecationWarning` that directs to DI. |
| **Tests Required** | 5 integration: (1) DI container creates all dependencies without errors, (2) two concurrent requests use separate agent instances, (3) test with mocked ChromaDB returns expected results, (4) lifespan-managed ChromaClient closes on shutdown, (5) graph compilation with injected deps succeeds. |

---

#### Issue #8 — No PostgresCheckpointer on Graph Compilation
| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Dependencies** | #3 (PostgreSQL), #2 (DI refactoring — checkpointer must be injected) |
| **Prerequisites** | #2 merged |
| **Files Affected** | `backend/graph/workflow.py` (add checkpointer parameter to compile), `backend/api/main.py` (initialize PostgresCheckpointer in lifespan, store in app.state, pass to graph compilation), `backend/core/config.py` (add `LANGGRAPH_CHECKPOINT_URI`) |
| **Complexity** | 4/10 |
| **Risk** | 3/10 — Checkpoint tables created on first run. If migration fails, graph refuses to compile. |
| **Breaking Changes** | None (checkpointing is transparent) |
| **Migration** | Alembic migration adds `checkpoints` and `checkpoint_blobs` tables. |
| **Tests Required** | 2 integration: (1) graph with checkpointer stores state in Postgres, (2) resume-from-checkpointer returns correct partial state. |

---

#### Issue #9 — Evaluation Runs Synchronously Inline
| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Dependencies** | #13 (RAGAS integration — needed for proper evaluation) |
| **Prerequisites** | #13 merged |
| **Files Affected** | `backend/graph/nodes.py:204` (remove `evaluator.evaluate_response(state)` from serving path, replace with queue push), `backend/graph/workflow.py` (remove `evaluation_node` from graph definition), New file `backend/workers/eval_worker.py` (Celery/Redis worker that consumes evaluation tasks) |
| **Complexity** | 5/10 |
| **Risk** | 4/10 — Offline evaluation may fail silently if worker is not running. |
| **Breaking Changes** | Response latency drops 3-8s. Any code awaiting evaluation results in the response must use new async pattern. |
| **Migration** | None |
| **Tests Required** | 2 unit: (1) evaluation node pushes to queue instead of computing inline, (2) worker processes queue item correctly. 1 integration: offline evaluation produces all RAGAS dimension scores. |

---

#### Issue #13 — No Actual RAGAS Integration
| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/agents/evaluation/agent.py` (complete rewrite: use `ragas` library, compute 4 dimensions, persist to DB), `backend/evaluation/benchmark.py` (refactor to use RAGAS), `pyproject.toml` (add `ragas`), new file `backend/evaluation/runner.py` (CLI orchestrator) |
| **Complexity** | 5/10 |
| **Risk** | 3/10 — RAGAS may have dependency conflicts with existing packages. Pin version. |
| **Breaking Changes** | `composite_score` field disappears from evaluation results, replaced by per-dimension scores. |
| **Migration** | Alembic migration adds columns for each RAGAS dimension to `evaluation_metrics`. |
| **Tests Required** | 3 unit: (1) faithfulness < 0.5 for hallucinated answer, (2) context_precision = 0.0 for irrelevant context, (3) all 4 dimensions returned. |

---

#### Issue #14 — No OpenTelemetry
| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Dependencies** | #2 (DI refactoring — tracer must be injected into nodes) |
| **Prerequisites** | #2 merged |
| **Files Affected** | `backend/core/telemetry.py` (replace placeholder with real OTel SDK), `backend/core/telemetry_collector.py` (deprecate custom functions, wrap OTel spans), `backend/graph/nodes.py` (add OTel span context managers), `backend/graph/runner.py` (create root span), `backend/api/main.py` (add FastAPIInstrumentor), `backend/core/config.py` (add OTel settings), `pyproject.toml` (add OTel packages) |
| **Complexity** | 5/10 |
| **Risk** | 4/10 — OTel exporter could block if endpoint is unreachable. Must configure `BatchSpanProcessor` with timeout. |
| **Breaking Changes** | Custom telemetry tables (`execution_traces`) stop receiving full data. Dual-write during transition. |
| **Migration** | None |
| **Tests Required** | 2 integration: (1) trace context propagates from HTTP to graph, (2) span attributes include correct phase/agent names. Manual validation with OTel console exporter. |

---

#### Issue #21 — No Streaming API
| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Dependencies** | None (independent feature) |
| **Prerequisites** | None |
| **Files Affected** | `backend/api/routers/query.py` (add SSE streaming endpoint), `backend/graph/nodes.py` (accept callback function for streaming events), `backend/graph/workflow.py` (pass streaming callback through execution context), `backend/graph/runner.py` (wire callback from HTTP → graph) |
| **Complexity** | 6/10 |
| **Risk** | 4/10 — Streaming adds complexity to graph execution. Callback pattern must be opt-in and not affect existing buffered path. |
| **Breaking Changes** | None (new endpoint, existing POST endpoint unchanged) |
| **Migration** | None |
| **Tests Required** | 2 integration: (1) SSE stream emits correct event sequence (intake → planning → retrieval → generation → critic → output), (2) SSE timeout handling works after 30s. |

---

#### Issue #18 — Only 2 Smoke Tests Exist
| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Dependencies** | #2 (DI — enables mocking deps in tests) |
| **Prerequisites** | #2 merged |
| **Files Affected** | `backend/tests/unit/` (13 new test files), `backend/tests/integration/` (5 new test files), `backend/tests/e2e/` (3 new test files), `backend/tests/conftest.py` (shared fixtures + mocked dependencies), `pyproject.toml` (pytest config with markers, coverage config) |
| **Complexity** | 7/10 |
| **Risk** | 3/10 — Risk of CI pipeline configuration issues |
| **Breaking Changes** | None |
| **Migration** | None |
| **Tests Required** | Target: 50+ unit, 10+ integration, 3+ E2E. Coverage: >80% agent code. |

---

#### Issue #19 — No Load Shedding or Request Queuing
| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Dependencies** | #1 (async Redis — needed for token bucket) |
| **Prerequisites** | #1 merged |
| **Files Affected** | `backend/api/middleware/rate_limit.py` (replace fixed-window with token bucket, add per-user burst limit), `backend/api/routers/query.py` (add semaphore guard around graph execution), `backend/graph/runner.py` (add timeout wrapper), `backend/core/config.py` (add concurrency/timeout settings) |
| **Complexity** | 4/10 |
| **Risk** | 3/10 — Token bucket implementation may have off-by-one errors in burst calculation. |
| **Breaking Changes** | Rate limit behavior shifts from fixed-window to token-bucket. Burst traffic at window boundary now counts against burst budget instead of passing through. May require tuning if existing clients relied on window-edge bursts. |
| **Migration** | None |
| **Tests Required** | 3 integration: (1) 6 concurrent requests → 5 execute, 1 returns 429, (2) rate limiter returns correct headers, (3) query timeout after 120s returns 504. |

---

#### Issue #22 — No API Versioning (Downgraded)
| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/api/main.py` (add `/v1` prefix explicit — it already exists, but add deprecation warning for non-versioned paths) |
| **Complexity** | 1/10 |
| **Risk** | 1/10 |
| **Breaking Changes** | None (prefix already exists) |
| **Migration** | None |
| **Tests Required** | 1 unit: `/api/v1/` routes return 200. |

---

#### Issue #23 — No Structured Logging Schema / PII in Logs
| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/core/logging.py` (add PII detection middleware, add log schema validation, add query text hashing) |
| **Complexity** | 3/10 |
| **Risk** | 2/10 — PII detection may have false positives (e.g., flagging "John Smith" in a public document as PII). |
| **Breaking Changes** | Log format changes. Any log parsing pipeline must be updated. Query text in logs appears as SHA-256 hash instead of plaintext. |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) email address in query → hashed in log, (2) SSN → hashed, (3) non-PII text → unchanged. |

---

#### Issue #24 — Prompt Injection Surface (No Defenses)
| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Dependencies** | None |
| **Prerequisites** | None |
| **Files Affected** | `backend/core/security.py` (add two-stage injection detection: regex first-pass + LLM-as-judge second-pass), `backend/api/middleware/rate_limit.py` (add injection-attempt rate limiting), `backend/graph/nodes.py` (add system prompt with injection resistance in generation node) |
| **Complexity** | 5/10 |
| **Risk** | 3/10 — LLM-as-judge adds latency (200-500ms per query). |
| **Breaking Changes** | 403 response for injection attempts. Legitimate queries with "ignore" or "system" text may be blocked. Tuning required. |
| **Migration** | None |
| **Tests Required** | 3 unit: (1) known injection pattern blocked, (2) obfuscated injection blocked, (3) legitimate query passes. Benchmark: 90%+ detection rate on OWASP Top 10 for LLM. |

---

#### Issue #17 (from REMEDIATION) — No RBAC / Audit Logging (Enhanced)
| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Dependencies** | #3 (PostgreSQL — audit log storage) |
| **Prerequisites** | #3 merged |
| **Files Affected** | `backend/storage/db/models.py` (add Role enum, User.role column, AuditLog table), `backend/api/routers/auth.py` (add role-based decorators, admin endpoints), `backend/api/middleware/rate_limit.py` (add audit logging middleware) |
| **Complexity** | 5/10 |
| **Risk** | 4/10 — Incorrect role checking could lock out legitimate users. |
| **Breaking Changes** | New `role` column on `users` table defaults to "viewer". Existing users need role assignment. |
| **Migration** | Alembic migration: add `role` column, create `audit_logs` table. Assign "admin" role to initial user. |
| **Tests Required** | 3 integration: (1) viewer cannot ingest (403), (2) admin can ingest (200), (3) audit log entry created for each mutating operation. |

---

## Optimized Phase Plan

---

### Phase 1: Infrastructure Foundation
**Goal:** Fix all crash/security blocker issues that require infrastructure changes. After this phase, the app runs on PostgreSQL, uses async Redis, has proper JWT secrets, and manages DB schema with Alembic.

**Files touched (grouped by logical change):**

| File | Changes | Issues |
|------|---------|--------|
| `backend/core/config.py` | Add SECRET_KEY, REDIS_POOL_SIZE, DATABASE_URL (Postgres), pool settings, CHROMA_ALLOW_RESET | #7, #1, #3, #25 |
| `backend/storage/db/session.py` | Remove SQLite fallback, add connection pooling, fail on Postgres unavailable | #3, #25 |
| `backend/memory/session.py` | Full rewrite: sync→async Redis, connection pool | #1 |
| `backend/core/security.py` | Remove hardcoded fallback secret, fail if SECRET_KEY missing | #7 |
| `backend/graph/nodes.py` | Minimal: add `await` on `get_history()` and `add_message()` | #1 |
| New: `backend/alembic/` | Alembic init, initial migration, env.py | #20 |

**Dependency ordering within Phase 1:**
1. `config.py` changes first (settings must exist before they're consumed)
2. `session.py` changes (requires new config settings)
3. Alembic init (requires Postgres from session.py)
4. `security.py` changes (requires new SECRET_KEY setting)
5. `session.py` async rewrite (requires new REDIS_POOL_SIZE setting)
6. `nodes.py` minimal await changes (requires async session.py)

**Validation criteria:**
- `make db-upgrade` creates all tables in Postgres
- `pytest backend/tests/ -k "postgres or redis or jwt"` passes
- App starts without SQLite or hardcoded secret
- 50 concurrent Redis writes under P99 < 200ms
- Missing SECRET_KEY causes startup failure

**Exit criteria:**
- [ ] PostgreSQL with connection pooling running in dev Docker Compose
- [ ] All SQLite references removed from `session.py`
- [ ] Alembic migration `001` creates all tables matching current models
- [ ] `redis.asyncio.Redis` replaces sync `redis.Redis` in `session.py`
- [ ] All `await` calls in place in `nodes.py`
- [ ] `SECRET_KEY` has no default, app fails at startup if missing
- [ ] `nexus_core.db` data migrated to Postgres
- [ ] Phase 1 test suite: 6 unit + 3 integration tests passing

---

### Phase 2: Critic Reliability & Retrieval Intelligence
**Goal:** Fix answer quality issues — correct hallucination detection, parallel verification, deterministic chunk IDs, adaptive retrieval, bounded state, and ChromaDB security. After this phase, the critic is reliable, retrieval is adaptive, and state is bounded.

**Files touched (grouped by logical change):**

| File | Changes | Issues |
|------|---------|--------|
| `backend/ingestion/chunker.py` | Return deterministic SHA-256 chunk IDs | #6 |
| `backend/ingestion/pipeline.py` | Propagate chunk IDs, add incremental indexing | #6, #12B |
| New: `backend/storage/document_registry.py` | Track indexed documents | #12B |
| `backend/storage/retriever.py` | Use ingested IDs, accept dynamic k, restructure graph results | #6, #12, #15 |
| `backend/storage/bm25.py` | Accept dynamic k parameter | #12 |
| `backend/storage/reranker.py` | Add fallback metric emission, health check | #17B |
| `backend/storage/vector/chroma.py` | Set allow_reset=False (env-controlled) | #17 |
| `backend/agents/critic/agent.py` | Fix empty claim handling, 4-way verdict tracking | #4, #5 |
| `backend/agents/critic/grounding_verifier.py` | Parallel per-claim verification with semaphore | #10 |
| `backend/graph/edges.py` | 4-branch routing instead of binary | #5 |
| `backend/graph/state.py` | Add complexity_score, target_k, BoundedList | #11, #12, #16 |
| `backend/graph/nodes.py` | Replace word count heuristic, use adaptive k, remove uuid4 chunk IDs | #6, #11, #12 |
| `backend/agents/healer/query_rewriter.py` | Accept healing_target parameter | #5 |
| `backend/core/config.py` | Add CHROMA_ALLOW_RESET setting | #17 |

**Minimal file touch count:** Every file in this list is touched exactly once in Phase 2. `nodes.py` gets its second touch (first was Phase 1 for async await, now for critic/retrieval logic).

**Dependency ordering within Phase 2:**
1. `state.py` adds new fields (they're consumed by everything else)
2. `chunker.py` + `pipeline.py` (chunk ID source of truth)
3. `retriever.py`, `bm25.py`, `reranker.py` (storage layer changes)
4. `chroma.py` (config change, independent)
5. `critic/agent.py` + `grounding_verifier.py` (agent changes)
6. `healer/query_rewriter.py` (healing strategy changes)
7. `edges.py` (routing changes, depends on critic verdict)
8. `nodes.py` (pipeline orchestration changes, depends on everything above)
9. `document_registry.py` + `pipeline.py` incremental indexing (can be parallel)

**Validation criteria:**
- Empty answer → `grounding_score=0.0`, `verification_mode="no_claims"`
- FULLY_SUPPORTED routes to output, PARTIALLY to healing with expansion target
- Parallel verification uses ≤5 concurrent LLM calls
- Same content in two documents → same SHA-256 chunk ID
- "GDPR Article 17 extraterritorial scope" (7 words) classified as complex → k=10+
- State with 25 chunks trims to 20, 15 errors trims to 10
- Graph results appear as separate `source: "knowledge_graph"` entries
- ChromaDB `reset()` returns 403
- Startup with 10,000 documents takes <1s (incremental indexing)
- Reranker fallback emits metric

**Exit criteria:**
- [ ] All 4-agent and storage layer changes implemented
- [ ] Chunk IDs deterministic via SHA-256
- [ ] Empty claim → score=0.0 (not 1.0)
- [ ] 4-way routing with correct healing strategies
- [ ] Parallel claim verification with semaphore
- [ ] Query complexity classifier replacing word count
- [ ] Adaptive k implemented (3/5/10/20)
- [ ] Bounded state lists (max 20 chunks, max 10 errors)
- [ ] Graph context as separate structured entries
- [ ] ChromaDB allow_reset=False (env-controlled)
- [ ] Incremental indexing with document registry
- [ ] Reranker fallback observable via metric
- [ ] Phase 2 test suite: 25+ unit + 2 integration tests passing

---

### Phase 3: Architecture & Observability
**Goal:** Replace module-level singletons with dependency injection, add PostgresCheckpointer, move evaluation offline with RAGAS, implement OpenTelemetry, and add SSE streaming. After this phase, the system is architecturally sound, observable, and user-friendly.

**Files touched (grouped by logical change):**

| File | Changes | Issues |
|------|---------|--------|
| `backend/graph/nodes.py` | DI factory (remove 11 singletons), add OTel spans, add streaming callback, remove inline evaluation | #2, #14, #9, #21 |
| `backend/graph/workflow.py` | Accept DI deps, accept checkpointer, accept streaming callback, remove evaluation node from graph | #2, #8, #21, #9 |
| `backend/graph/runner.py` | Accept injected graph, add root OTel span, wire streaming callback, add timeout wrapper | #2, #14, #21 |
| `backend/api/main.py` | DI container in lifespan, PostgresCheckpointer init, FastAPIInstrumentor, store deps in app.state | #2, #8, #14 |
| `backend/api/routers/query.py` | Use DI graph from app.state, add SSE streaming endpoint | #2, #21 |
| `backend/core/telemetry.py` | Real OTel SDK initialization with OTLP exporter | #14 |
| `backend/core/telemetry_collector.py` | Deprecate custom functions, wrap OTel spans | #14 |
| `backend/core/config.py` | Add OTel settings, LANGGRAPH_CHECKPOINT_URI | #14, #8 |
| `backend/agents/evaluation/agent.py` | Full rewrite: RAGAS integration, offline pattern | #13 |
| `backend/evaluation/benchmark.py` | Refactor to use RAGAS | #13 |
| New: `backend/evaluation/runner.py` | CLI orchestrator for offline evaluation | #13 |
| New: `backend/workers/eval_worker.py` | Celery/Redis worker for async evaluation | #9 |
| `pyproject.toml` | Add OTel packages, ragas | #13, #14 |

**Minimal file touch count:** `nodes.py` gets its third and final touch. `workflow.py`, `main.py`, `runner.py`, `query.py` get their first touch.

**Dependency ordering within Phase 3:**
1. `config.py` adds OTel + checkpoint settings (consumed by everything)
2. `telemetry.py` + `telemetry_collector.py` (OTel infrastructure)
3. `evaluation/agent.py` + `benchmark.py` + `runner.py` + `eval_worker.py` (RAGAS + offline eval)
4. `nodes.py` DI factory + OTel spans + streaming callback + eval removal (one comprehensive refactor)
5. `workflow.py` accept DI + checkpointer + streaming callback + remove eval node
6. `runner.py` accept injected graph + root span + streaming + timeout
7. `main.py` DI container + checkpointer init + instrumentor + app.state wiring
8. `query.py` use DI graph + SSE endpoint

**Validation criteria:**
- Two concurrent requests use separate agent instances
- Graphs with mocked ChromaDB return expected test results
- Mid-pipeline failure resumes from last checkpoint
- SSE stream emits correct event sequence: intake → planning → retrieval → generation → critic → output
- OpenTelemetry traces appear with spans for every graph node
- LangSmith shows LLM call traces
- Response latency drops 3-8s (evaluation moved offline)
- RAGAS evaluation produces faithfulness, answer_relevance, context_precision, context_recall
- Evaluation worker processes queued items correctly

**Exit criteria:**
- [ ] All 11 singletons removed from `nodes.py`, replaced by DI factory
- [ ] `workflow.py` accepts injected dependencies (no module-level `rag_graph`)
- [ ] PostgresCheckpointer initialized in lifespan, passed to graph compilation
- [ ] SSE streaming endpoint (`GET /v1/query/stream`) returns correct event sequence
- [ ] Evaluation node removed from serving graph, replaced by offline queue push
- [ ] RAGAS integrated: per-dimension scores computed offline
- [ ] Real OpenTelemetry with OTLP exporter, spans in every graph node
- [ ] Custom telemetry collector deprecated (dual-write during transition)
- [ ] Phase 3 test suite: 14+ unit + 6+ integration tests passing
- [ ] Manual validation: trace appears in Jaeger/Tempo, SSE stream in browser

---

### Phase 4: Security Hardening & Production Readiness
**Goal:** Add RBAC + audit logging, test infrastructure, load shedding, prompt injection defense, PII redaction, and deployment hardening. After this phase, the system is production-ready.

**Files touched (grouped by logical change):**

| File | Changes | Issues |
|------|---------|--------|
| `backend/storage/db/models.py` | Add Role enum, User.role, AuditLog table | RBAC |
| `backend/api/routers/auth.py` | Role decorators, admin user management endpoints | RBAC |
| `backend/api/middleware/rate_limit.py` | Token bucket algorithm, burst limit, injection-attempt rate limit, audit logging | #19, #24 |
| `backend/core/security.py` | Two-stage injection detection (regex + LLM-as-judge) | #24 |
| `backend/core/logging.py` | PII detection + redaction, log schema validation | #23 |
| `backend/graph/nodes.py` | Add system prompt with injection resistance | #24 |
| `backend/graph/runner.py` | Timeout wrapper (moved from Phase 3 if not done) | #19 |
| `backend/api/main.py` | Add `/v1` prefix deprecation warning | #22 |
| New: `backend/tests/unit/*.py` | 13 test files with mocked dependencies | #18 |
| New: `backend/tests/integration/*.py` | 5 test files with real Docker services | #18 |
| New: `backend/tests/e2e/*.py` | 3 end-to-end test files | #18 |
| `backend/tests/conftest.py` | Shared fixtures, mocked agents, test DB | #18 |
| `pyproject.toml` | Pytest config, coverage targets, test markers | #18 |
| `docker-compose.yml` | Resource limits, healthchecks, restart policy | Deploy |
| `infra/k8s/api.yaml` | HPA, PDB, secrets, probes | Deploy |
| `infra/docker/Dockerfile.api` | Non-root user, multi-stage build | Deploy |
| New: `infra/monitoring/` | Prometheus config + Grafana dashboard | Deploy |

**Minimal file touch count:** `main.py` gets its second touch (first was Phase 3 for DI). `security.py` gets its second touch (first was Phase 1 for JWT). `config.py` gets its second touch (first was Phase 1 for infra settings). No other file is re-touched.

**Dependency ordering within Phase 4:**
1. `logging.py` PII redaction (independent)
2. `security.py` injection detection (independent)
3. `models.py` + `auth.py` RBAC (independent)
4. `rate_limit.py` load shedding + injection rate limit (independent)
5. `nodes.py` system prompt (independent, minimal change)
6. `main.py` API versioning (independent)
7. Test infrastructure (depends on DI from Phase 3)
8. Deployment hardening (depends on all above merged)

**Validation criteria:**
- Token bucket algorithm allows bursts up to `burst_limit` within sustained rate
- 6 concurrent requests → 5 execute, 1 returns 429 with correct headers
- 10 known prompt injection patterns → 9+ detected
- 100 legitimate queries → 0 flagged as injection
- PII in query text → SHA-256 hash in logs
- `viewer` role receives 403 on ingest, `admin` receives 200
- Every mutating API call creates audit log entry
- `make test` runs 60+ tests with >80% coverage
- Docker Compose starts all services with healthchecks passing
- K8s apply creates pods with correct resource limits and secrets

**Exit criteria:**
- [ ] Test infrastructure complete: 50+ unit, 10+ integration, 3+ E2E tests
- [ ] All tests passing with >80% agent code coverage
- [ ] RBAC implemented: viewer/editor/admin roles, admin endpoints
- [ ] Audit logging for all mutating operations
- [ ] Load shedding: token bucket rate limiter, concurrency semaphore, query timeout
- [ ] Prompt injection: two-stage detection (regex + LLM-as-judge) with 90%+ detection rate
- [ ] PII redaction in logs (email, SSN, names → hashed)
- [ ] API versioning with `/api/v1/` prefix
- [ ] Docker Compose resource limits, healthchecks, non-root user
- [ ] K8s deployment: HPA, PDB, secrets, readiness/liveness probes
- [ ] Prometheus + Grafana monitoring dashboards
- [ ] Phase 4 test suite: 15+ unit + 10+ integration + 3+ E2E tests passing

---

## Cross-Phase Optimization Summary

### Files That Appear in Multiple Phases

| File | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Rationale for Multiple Touches |
|------|---------|---------|---------|---------|-------------------------------|
| `nodes.py` | Minimal `await` adds | Critic/retrieval logic | DI+OTel+streaming | — | Cannot do before infrastructure is stable |
| `main.py` | — | — | DI container init | API versioning | Different concerns, DI is prerequisite for RBAC |
| `security.py` | JWT secret | — | — | Injection detection | Unrelated concerns, but could merge if desired |
| `config.py` | Infra settings | — | OTel settings | — | Settings added as features require them |

### Files Touched Exactly Once (10+ files)

| File | Phase | Change |
|------|-------|--------|
| `session.py` | 1 | Async Redis + Postgres pooling |
| `state.py` | 2 | New fields + BoundedList |
| `chroma.py` | 2 | allow_reset=False |
| `retriever.py` | 2 | Chunk IDs + dynamic k + graph restructure |
| `bm25.py` | 2 | Dynamic k |
| `reranker.py` | 2 | Fallback metric |
| `critic/agent.py` | 2 | Empty claims + 4-way verdict |
| `grounding_verifier.py` | 2 | Parallel verification |
| `edges.py` | 2 | 4-way routing |
| `chunker.py` | 2 | Deterministic IDs |
| `pipeline.py` | 2 | Chunk IDs + incremental indexing |
| `evaluation/agent.py` | 3 | RAGAS + offline |
| `telemetry.py` | 3 | Real OTel |
| `telemetry_collector.py` | 3 | OTel wrapper |
| `query.py` | 3 | DI + SSE |
| `runner.py` | 3 | Injected graph + OTel + streaming |
| `rate_limit.py` | 4 | Token bucket + injection limit |
| `logging.py` | 4 | PII redaction |
| `models.py` | 4 | RBAC + audit log |

### Maximum File Touch Count: 3 (`nodes.py`)
This is unavoidable because:
1. Phase 1: Add `await` to existing Redis calls (cannot do later — blocks event loop)
2. Phase 2: Replace retrieval/critic logic (must do after infrastructure stable)
3. Phase 3: DI refactoring + OTel + streaming (must do after Phase 2 logic is correct and tested)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Phase 3 DI refactoring breaks graph execution | High | Critical | Test pyramid from Phase 4 should ideally come before, but it depends on DI. Mitigation: feature-flag new DI path, run both in parallel for 1 week. |
| Phase 2 critic changes introduce false positives | Medium | High | Add monitoring on `grounding_score` distribution pre/post deploy. Rollback if >10% shift. |
| Phase 1 PostgreSQL migration loses data | Low | High | Dry-run migration. Keep `nexus_core.db` snapshot. |
| Phase 3 streaming callback adds latency to buffered path | Low | Medium | Profile both paths. Default to buffered, opt-in to streaming. |
| Phase 4 prompt injection LLM-as-judge blocks legitimate queries | Medium | Medium | Run in "log-only" mode for 1 week to calibrate thresholds. |
| Concurrent work on same files across branches | Medium | Medium | Phase ordering ensures no two phases touch the same file at the same time. Use feature branches per phase. |

---

## Total Effort Estimate

| Phase | Duration | Files Changed | Tests Added | Risk |
|-------|----------|---------------|-------------|------|
| Phase 1: Infrastructure Foundation | 3-4 days | 6 + Alembic init | 9+ (6 unit, 3 integration) | Medium (PostgreSQL migration) |
| Phase 2: Critic & Retrieval | 5-7 days | 14 | 27+ (25 unit, 2 integration) | Medium (critic behavior change) |
| Phase 3: Architecture & Observability | 7-10 days | 12 + 2 new files | 20+ (14 unit, 6 integration) | High (DI refactoring) |
| Phase 4: Security & Production | 7-10 days | 15 + 25 test files | 28+ (15 unit, 10 integration, 3 E2E) | Medium (injection false positives) |
| **Total** | **22-31 days** | **~50 files** | **84+ tests** | |

---

## Appendix: Issue Number Reference (REMEDIATION_PLAN.md → This Plan)

| Remedi. Plan # | Issue | Phase | Priority in Phase |
|----------------|-------|-------|-------------------|
| 1 | Sync Redis blocking async event loop | 1 | 3rd |
| 2 | Module-level global singletons | 3 | 1st |
| 3 | SQLite fallback corrupts | 1 | 1st |
| 4 | Empty claims → perfect grounding score | 2 | 3rd |
| 5 | Binary critic → 4-way routing | 2 | 4th |
| 6 | Chunk IDs missing (empty strings) | 2 | 2nd |
| 7 | HS256 JWT with hardcoded fallback secret | 1 | 2nd |
| 8 | No PostgresCheckpointer | 3 | 2nd |
| 9 | Evaluation runs synchronously inline | 3 | 4th |
| 10 | Batch claim verification in single LLM call | 2 | 5th |
| 11 | Word count as query complexity heuristic | 2 | 6th |
| 12 | Hardcoded k=5 with no adaptive top-k | 2 | 7th |
| 12B | Re-embedding entire corpus on startup | 2 | 8th |
| 13 | No actual RAGAS integration | 3 | 3rd |
| 14 | No OpenTelemetry | 3 | 5th |
| 15 | Graph context prepended as string to first chunk | 2 | 9th |
| 16 | Unbounded state size | 2 | 10th |
| 17 | ChromaDB allow_reset=True | 2 | 11th |
| 17B | Reranker silently falls back | 2 | 12th |
| 18 | Only 2 smoke tests exist | 4 | 1st |
| 19 | No load shedding or request queuing | 4 | 2nd |
| 20 | No Alembic migrations directory | 1 | 4th |
| 21 | No streaming API | 3 | 6th |
| 22 | No API versioning (downgraded) | 4 | 3rd |
| 23 | No structured logging / PII in logs | 4 | 4th |
| 24 | Prompt injection surface (no defenses) | 4 | 5th |
| 25 | No DB connection pooling | 1 | 5th (done with #3) |