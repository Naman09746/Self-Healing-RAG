# Staff-Level Architecture Review
## Self-Healing Multi-Agent RAG Platform

> **Reviewer persona:** Principal AI Architect / Staff GenAI Engineer / Distributed Systems Architect  
> **Review mode:** Production Design Review — no diplomacy  
> **Assumptions:** 100K+ documents, multi-user enterprise, real SLAs, real compliance

---

## EXECUTIVE VERDICT (Read This First)

This blueprint is **a well-structured junior-to-mid senior deliverable** that will **not** impress Staff engineers at OpenAI, Anthropic, or Google DeepMind in its current state.

The documentation is excellent. The thinking is correct. The vocabulary is right. But the **actual code diverges critically from the blueprint**, and both the blueprint and code have **fundamental architectural holes** that production AI systems cannot have. The gap between what is documented and what is implemented is where this project lives or dies.

I am going to enumerate every weakness, tell you exactly why it fails in production, and tell you exactly what to build instead.

---

## TASK 1 — Subsystem Scores (1–10)

### Retrieval Layer — **5/10**

**What's there:** Hybrid retrieval with RRF, cross-encoder reranking, ChromaDB.

**What's broken:**

1. **`chunk_id` is generated with `uuid.uuid4()` at retrieval time** ([nodes.py L104](../backend/graph/nodes.py#L104)). This is catastrophically wrong. Chunk IDs must be deterministic content-hashes at ingestion time. A fresh UUID at retrieval time means: (a) citation tracking is broken — you can never re-fetch the source, (b) deduplication is broken, (c) the retry controller's "stuck chunk" detection compares IDs that are different every time even for identical content.

2. **`k=5` hardcoded** ([nodes.py L95](../backend/graph/nodes.py#L95)). Fixed k with no adaptive top-k based on query complexity, document corpus density, or retrieval score distribution. A complex multi-hop legal question needs k=20. A simple factual lookup needs k=3. Static k destroys recall precision balance.

3. **No BM25 fallback path in the actual workflow graph.** The blueprint documents it extensively. The code has a single `HybridRetriever` with no strategy switching. The `AdaptiveRetrievalSelector` doesn't exist in the implementation.

4. **No metadata filtering.** The retrieval call has no tenant isolation, date filtering, or document type filtering. In a multi-user enterprise system, this means User A's query retrieves User B's confidential documents. This is a **security vulnerability**, not just a bug.

5. **Chunking strategy is undocumented in the codebase.** The blueprint has an excellent chunking matrix but the actual ingestion pipeline appears to use a single fixed chunker.

**Production failure mode:** At 100K documents, retrieval precision collapses without metadata filtering. The security boundary violation alone makes this undeployable in enterprise.

---

### Memory Layer — **3/10**

**What's there:** Session memory in Redis, semantic memory concept, query cache.

**What's broken:**

1. **Session memory is synchronous** ([nodes.py L42](../backend/graph/nodes.py#L42)). `session_memory.get_history()` is called without `await`. In an async FastAPI + LangGraph stack, blocking sync calls in the event loop are a latency bomb. Under 50 concurrent users, this creates a convoy effect.

2. **No episodic memory.** The system has no concept of "what happened in past sessions for this user that should inform retrieval today." Semantic memory is described but implemented as a simple query cache wrapper. This is not semantic memory — it's a key-value store with vector search bolted on.

3. **No procedural memory.** There is zero learning from healing events. The `RetryMemory` described in the blueprint does not exist in the codebase. The system makes the same retrieval mistakes on identical query patterns repeatedly because it never learns which healing strategies worked for which failure modes.

4. **Memory isolation is completely absent.** `SemanticQueryCache.cache_query()` stores answers globally without any user or tenant scoping. User A's query for "quarterly results" returns User B's cached answer about their quarterly results. This is a **GDPR/HIPAA compliance failure** in any enterprise deployment.

5. **Memory lifecycle management is undefined.** What is the eviction policy beyond TTL? High-quality memories should persist longer. Low-quality interactions should be evicted. There is no quality-weighted retention.

**Production failure mode:** Memory cross-contamination between users is a critical data breach. The system will be non-compliant in any regulated industry within the first week of multi-user operation.

---

### Agent Architecture — **4/10**

**What's there:** LangGraph graph with 8 nodes. Planner, retrieval, generation, critic, healer, evaluator agents.

**What's broken:**

1. **All agents are instantiated as module-level global singletons** ([nodes.py L21-31](../backend/graph/nodes.py#L21-31)). `store = ChromaStore()`, `generator = GenerationAgent()`, etc. — all created at import time. This means: (a) no dependency injection, (b) no testability — every test imports real agents, (c) no ability to swap models per request, (d) all worker processes share the same agent instances with no isolation guarantees.

2. **The `planning_node` uses word count to decide query complexity** ([nodes.py L76](../backend/graph/nodes.py#L76)). A 7-word question like "What are the legal implications of GDPR Article 17?" is not simple. A 15-word rambling query can be trivial. Word count as a complexity heuristic is embarrassingly naive. This should be an LLM classifier or at minimum an embedding-based similarity to a complexity distribution.

3. **No agent specialization.** Every agent runs the same base model. A real multi-agent system routes different sub-tasks to specialized models. Extraction (small, fast), generation (medium, quality), critique (specialized NLI or Judge LLM), evaluation (different from generation). The entire system currently runs through a single LLM endpoint with different prompts — that's not multi-agent architecture, that's a sequence of LLM calls.

4. **Agents have no state isolation between requests.** If a request fails mid-graph, the shared global agent instances may hold stale state from the previous request.

5. **No agent communication protocol.** Agents communicate exclusively through the LangGraph state object. This is correct in principle, but the state design is under-specified. Critical context like *why* a previous retrieval failed is not carried forward in a structured way, only as raw error strings in `error_log`.

**Production failure mode:** Module-level singletons will deadlock under concurrent load. Two requests competing for the same `ChromaStore()` instance with no connection pooling is a production P0.

---

### Hallucination Detection — **5/10**

**What's there:** Claim extraction + grounding verification via LLM, binary `is_hallucinated` flag.

**What's broken:**

1. **The critic gives a binary verdict** ([edges.py L18](../backend/graph/edges.py#L18)). `is_hallucinated: bool` and `grounding_score: float`. The blueprint has FULLY_SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED / CONTRADICTED — the code has SUPPORTED / CONTRADICTED. The nuance between "claim is not mentioned" and "claim actively contradicts source" is critical: they should trigger different healing strategies. Both currently trigger the same `healing_node` with the same `query_rewriter`.

2. **Claim extraction failure is a silent pass** ([agent.py L24-25](../backend/agents/critic/agent.py#L24-25)). `if not claims: return grounding_score=1.0`. A one-word answer, a refusal, or a model failure that returns no extractable claims is treated as **perfect grounding**. This is the exact opposite of correct behavior. Zero claims extracted should be treated as `grounding_score=0.0` or trigger a special verification path.

3. **No citation validation** exists in the actual code. The blueprint documents it in detail. The critic returns no citation data structure. The `output_node` stores no citation metadata. Users get answers with no ability to verify sources.

4. **The grounding verifier sends all claims in ONE LLM call** ([agent.py L28](../backend/agents/critic/agent.py#L28)). "Batch mode" for claim verification over many context chunks overwhelms the model's context window and causes verdict drift — the model starts making holistic judgments rather than per-claim atomic verdicts. Per-claim verification with parallel async calls is correct.

5. **No self-calibration.** The `GROUNDING_THRESHOLD` is a hardcoded constant. Different query types, different domains, and different document types warrant different thresholds. A legal contract QA system needs threshold=0.95. A creative content assistant can tolerate 0.6.

**Production failure mode:** At scale, silent claim extraction failures will produce `grounding_score=1.0` for refusals, hallucinated summaries of empty contexts, and degenerate answers — all served to users as fully grounded.

---

### Evaluation Framework — **3/10**

**What's there:** An `EvaluationAgent` that computes a composite score.

**What's broken:**

1. **RAGAS is not actually integrated.** The blueprint promises RAGAS metrics (faithfulness, answer relevance, context precision, context recall). The `evaluation_node` calls `evaluator.evaluate_response(state)` which returns a `composite_score` — this is a custom, undefined formula, not RAGAS. Saying "RAGAS-compatible" in a portfolio project when RAGAS is not integrated is misleading.

2. **Evaluation runs inline on every query** ([workflow.py L51](file://Users/namanjoshi/Workplace/Self-Healing-AI-Agent/backend/graph/workflow.py#L51)). Evaluation is a node in the live serving path. RAGAS evaluation adds 3-8 seconds per query. Running it synchronously in the response path means your P99 latency is 25+ seconds minimum. Evaluation must be async/offline.

3. **No ground-truth comparison.** Evaluation without reference answers measures internal consistency, not correctness. Faithfulness checks if the answer is supported by retrieved context — but if your retrieval is wrong, faithfulness is high and correctness is zero.

4. **No evaluation regression pipeline.** The `eval_dataset.jsonl` is mentioned but doesn't exist in the codebase. There is no `scripts/run_eval.py`. The CI pipeline has no evaluation gate.

5. **No A/B framework.** You cannot compare model A vs model B on your eval set without infrastructure to run parallel experiments with the same dataset and compare metric distributions statistically.

**Production failure mode:** Without a ground-truth regression pipeline, any model change can silently degrade quality. In 3 months, your faithfulness numbers will have drifted 20% and no alarm will fire.

---

### Observability — **4/10**

**What's there:** `telemetry_collector.log_trace()` calls, structured logging with `get_logger`.

**What's broken:**

1. **OpenTelemetry is described but not visible in actual instrumentation.** The `telemetry_collector.log_trace()` is a custom homegrown telemetry system, not OpenTelemetry SDK spans. This means no distributed trace correlation across services, no compatibility with Jaeger/Tempo/Honeycomb, and no W3C trace context propagation between the FastAPI layer and LangGraph.

2. **No LangSmith integration exists in the code.** The blueprint mentions it. There is zero LangSmith SDK initialization anywhere in the codebase. This means zero LLM call tracing, zero prompt/response logging, zero LangGraph run visualization.

3. **Prometheus metrics are not defined anywhere in the implementation.** The blueprint has an excellent metrics list. None of those counters/histograms appear to be instantiated in the actual codebase.

4. **No trace ID propagation.** The `trace_id` field exists in `RAGState` but there is no OpenTelemetry context propagation connecting the FastAPI request trace to the LangGraph execution trace. Every node creates its own isolated log event.

5. **The telemetry collector writes to... what?** The `log_trace()` call signature suggests it might be writing to a database, but without seeing the implementation it's unclear if this is a file, Redis, Postgres, or stdout. If it's synchronous database writes in the hot path, it adds latency to every node execution.

**Production failure mode:** When a user reports a wrong answer, you have no ability to reconstruct the full execution trace. You cannot correlate the retrieval strategy, the exact chunks retrieved, the model prompt, the critic verdict, and the healing decision for a specific request. You are flying blind.

---

### Security — **4/10**

**What's there:** Auth middleware concept, PII patterns, injection detection regex.

**What's broken:**

1. **Regex-based prompt injection detection** ([BLUEPRINT L1757](SELF_HEALING_RAG_BLUEPRINT.md#L1757)). A static list of injection patterns ("ignore previous instructions", "system prompt", etc.) is defeated by any attacker in 10 minutes. Jailbreaks use unicode homoglyphs, base64 encoding, gradual instruction builds, and language model quirks. A regex blocklist provides false security.

2. **JWT secret is HS256** ([BLUEPRINT L1819](SELF_HEALING_RAG_BLUEPRINT.md#L1819)). HS256 with a shared secret means any service with the secret can forge tokens. Enterprise deployments must use RS256/ES256 with asymmetric keys, where only the auth server holds the private key.

3. **No tenant isolation in vector store.** Documents from all users/tenants are in the same ChromaDB collection. A properly scoped query with a metadata filter can be bypassed by an attacker manipulating query parameters. Tenants must be in separate namespaces/collections with enforced filtering at the storage layer, not the application layer.

4. **No document provenance validation.** Who uploaded a document? Is the source trusted? A poisoning attack (uploading a document that says "our company's policy is that refunds are never allowed") has no countermeasure in this architecture.

5. **Rate limiting state stored in Redis without atomic operations.** The token bucket pattern without Lua scripts is subject to race conditions under concurrent requests, allowing burst traffic to bypass rate limits.

**Production failure mode:** The first enterprise customer will have a penetration test performed. Vector store cross-tenant access and HS256 JWT forgery will be P0 findings that delay production launch by months.

---

### Deployment — **5/10**

**What's there:** Docker Compose, Kubernetes manifests with HPA, CI/CD YAML.

**What's broken:**

1. **ChromaDB is deployed as a stateful service with a volume mount.** ChromaDB is not horizontally scalable. Two Kubernetes pods writing to the same ChromaDB instance creates write conflicts. Your HPA scales the API pods but ChromaDB remains a single point of failure. Under load, ChromaDB write latency increases and becomes the bottleneck.

2. **Ollama is CPU-fallback but GPU is the primary.** In a K8s deployment with GPU node pools, GPU nodes are expensive and slow to autoscale. A sudden traffic spike cannot be absorbed by spinning up GPU nodes in 3-5 minutes. There is no pre-warming strategy.

3. **No canary deployment.** Blue-green is described but not implemented in the K8s manifests. Canary deployments (10% traffic to new version, monitor quality metrics, then roll forward) are essential when changing LLM models or prompts — a bad prompt change should not hit all users.

4. **No secrets rotation strategy.** Vault is mentioned but there is no secret rotation protocol. API keys for OpenAI/Anthropic rotate, and the system has no mechanism to pick up new secrets without redeployment.

5. **No multi-region or DR plan.** For enterprise with SLAs, single-region deployment means any cloud provider AZ failure takes the system down.

---

### Data Layer — **4/10**

**What's there:** Postgres schema, Redis caching, ChromaDB vector store.

**What's broken:**

1. **`nexus_core.db` is a SQLite file in the project root.** This file exists in the actual filesystem. This is not the Postgres schema from the blueprint — there is a SQLite database being used somewhere in the implementation. SQLite under concurrent async access will produce `database is locked` errors under any realistic load.

2. **No connection pooling configuration is visible.** SQLAlchemy async requires explicit pool sizing. Default pools are 5 connections — catastrophically insufficient at 100 concurrent users.

3. **Vector store migration path is undefined.** The blueprint says ChromaDB → Pinecone is "a single implementation swap." In practice, re-embedding 100K documents at Pinecone's ingestion rate takes hours. There is no migration tooling, no dual-write strategy, no validation framework.

4. **No Alembic migrations directory** exists in the codebase. The database schema evolution is undefined. How do you add a column to `messages` without downtime?

5. **Postgres is single instance.** No read replicas. The audit trail writes (hallucination_events, healing_events, citations) compete with read queries for monitoring dashboards on the same connection pool.

---

### API Layer — **6/10**

**What's there:** FastAPI, routers for query/ingest/health, middleware concepts.

**What's better than average:** The blueprint's API design is actually solid. Schema-first with Pydantic, global exception mapping, health probes, structured error responses. This is the strongest component in the blueprint.

**What's still broken:**

1. **No request queuing.** Requests go directly to LangGraph execution. Under burst load, you have no backpressure mechanism. A traffic spike causes all requests to start executing simultaneously, overwhelming GPU memory and causing OOM errors on the Ollama instance.

2. **No streaming API.** All responses are buffered until the full pipeline completes. For a 30-second pipeline with healing cycles, users wait 30 seconds for any feedback. Enterprise users need SSE/WebSocket streaming with partial results.

3. **No API versioning.** `POST /query` with no version prefix. When you need to change the response schema (add citation fields, change confidence format), you break all clients.

---

### State Management — **5/10**

**What's there:** `RAGState` TypedDict, LangGraph state flow.

**What's broken:**

1. **State is compiled to a singleton** ([workflow.py L57](../backend/graph/workflow.py#L57)). `rag_graph = create_rag_graph()` at module level. Across concurrent requests, LangGraph uses separate state instances per invocation — this part is fine. But when the graph itself needs updating (model swap, prompt change), you must redeploy. There is no hot-reload mechanism.

2. **No Postgres checkpointer.** The blueprint says `g.compile(checkpointer=PostgresCheckpointer())`. The actual code compiles with no checkpointer. This means if a request fails mid-graph, there is zero recovery capability. The user gets an error with no ability to resume from the point of failure.

3. **State size is unbounded.** `retrieval_history: Annotated[list, add]` accumulates every retrieval attempt. Over 3 healing cycles with 5 chunks each, the state object grows. The `error_log` appends indefinitely. There are no state size limits.

---

## TASK 2 — Missing Enterprise-Grade Features

### Critical Gaps (Will block enterprise sales):

| Missing Feature | Impact | Why It Matters |
|---|---|---|
| **Human-in-the-Loop (HITL) Review** | CRITICAL | No enterprise AI system deploys without human review gates for high-stakes outputs. Legal, medical, financial domains require it by regulation. |
| **Multi-tenancy / Tenant Isolation** | CRITICAL | Single-tenant vector store means security breach. Every enterprise deployment requires namespace isolation. |
| **Audit Trail with Tamper-Proof Logging** | CRITICAL | SOC2, HIPAA, GDPR require immutable audit logs of who queried what, what was retrieved, what was answered. Your current logging is mutable. |
| **Access Control / RBAC** | CRITICAL | Different users should access different document collections. Currently there is no document-level access control. |
| **PII Redaction in Logs** | CRITICAL | You log queries. Queries contain PII. This is a GDPR violation in production. |

### Important Gaps (Reduce competitive differentiation):

| Missing Feature | Impact | Description |
|---|---|---|
| **Knowledge Graph RAG** | HIGH | Entity-relationship retrieval for multi-hop questions. "Who reported to the CEO who approved project X?" cannot be answered with vector search alone. |
| **Multi-hop Retrieval** | HIGH | Questions requiring synthesis across 3+ documents with reasoning chains. Current architecture retrieves once per attempt. |
| **Long-term Memory with Personalization** | HIGH | User preferences, domain expertise, interaction style should influence retrieval. |
| **Active Learning / Feedback Loops** | HIGH | Thumbs up/down on answers should feed back into retrieval quality improvement. |
| **Query Routing / Model Routing** | HIGH | Simple queries should hit cheap models. Complex questions should route to frontier models. Current system uses the same model for all queries. |
| **Streaming Responses** | HIGH | 30-second wait with no feedback is unacceptable in a product. |
| **Document Versioning** | MEDIUM | When a document is updated, stale chunks in the vector store cause incorrect answers. No version management exists. |
| **Workflow Checkpoints / Resume** | MEDIUM | No checkpoint means failed long-running requests cannot be resumed. Users lose all progress. |
| **Conflict Resolution** | MEDIUM | When two retrieved chunks directly contradict each other, the system has no principled reconciliation. |
| **Confidence Calibration** | MEDIUM | Is your 0.8 grounding score actually 80% reliable? Without calibration data, confidence scores are meaningless numbers. |
| **Cost Tracking per Request** | MEDIUM | You have no per-request token accounting. Enterprise customers need cost attribution by user, team, or use case. |
| **Reinforcement Learning from Feedback** | LOW | RL optimization of retrieval parameters based on user feedback. Long-term competitive moat. |

---

## TASK 3 — How FAANG/AI Labs Would Redesign This

### OpenAI Would Build It

OpenAI would not use LangGraph. They'd build the orchestration layer using their own **Swarm** or **Agents SDK** with:

- **Tool-calling as the primitive.** Every "agent" is a function registered as a tool. The orchestrator LLM decides which tools to call, in what order, with what parameters. This is more flexible than a compiled graph and handles emergent tool-use patterns.
- **Structured outputs everywhere.** Every tool call returns a Pydantic model, not a dict. No unstructured string parsing.
- **Model routing by task class.** `gpt-4o-mini` for extraction and routing. `gpt-4o` for generation. A fine-tuned NLI model for claim verification. `text-embedding-3-large` with Matryoshka embeddings for retrieval.
- **Evals as a first-class product.** They would build the eval framework first, define metrics, then build the system to meet those metrics. Not the other way around.
- **No Ollama in production.** Self-hosted inference is an anti-pattern at scale. They use vLLM with OpenAI-compatible API, deployed on A100/H100 clusters, with autoscaling.

### Anthropic Would Build It

Anthropic's focus is on **safety and honesty as engineering constraints**:

- **Constitutional AI integration.** The critic doesn't just check grounding — it checks every response against a set of constitutional principles (harmlessness, truthfulness, non-manipulation). Violations trigger a revision cycle, not just a retrieval retry.
- **Interpretability tooling built in.** Every response includes a chain-of-thought that is separately evaluated. Anthropic would instrument the reasoning trace and build dashboards to detect reasoning failures.
- **Prompt injection as a first-class security boundary.** They would implement a two-stage pipeline: run input through a safety classifier before it ever touches the retrieval system. Not regex — an actual fine-tuned classifier.
- **RLHF data pipeline.** Every interaction is stored in a format suitable for preference optimization. The system collects comparison data (answer A vs answer B) and periodically fine-tunes the critic model.
- **Claude's extended thinking for critic.** Budget tokens explicitly for multi-step reasoning in the hallucination verification step. Shallow reasoning produces unreliable verdicts.

### Google DeepMind Would Build It

DeepMind would approach this as a **research-grade system with production hardening**:

- **Grounding through search.** Deep integration with Google Search / Vertex AI Search for web-scale grounding. Local document retrieval is augmented with real-time web search for recency.
- **AlphaProof-style verification.** For factual claims with verifiable answers (dates, numbers, proper nouns), DeepMind would implement formal verification — not LLM-based, but rule-based verification against structured knowledge bases (Wikidata, domain ontologies).
- **Speculative decoding at inference.** Rather than generating one answer and then critiquing it, generate multiple candidate answers in parallel using speculative decoding, then select the most grounded one.
- **Gemini 1.5 million token context for large document sets.** Rather than chunking, for documents ≤ 1M tokens, use full-context retrieval with Gemini's native long context. Chunking is a workaround for context limits that DeepMind has partially solved.
- **Multimodal from day one.** PDFs with figures, diagrams, tables — all processed natively with Gemini's multimodal capabilities, not OCR → text → embedding workarounds.

### Microsoft Would Build It

Microsoft builds for **Azure enterprise integration**:

- **Azure AI Search as the retrieval backbone.** Semantic + hybrid search, built-in reranking via Azure AI Reranker, integrated with Microsoft Purview for compliance-aware retrieval.
- **Copilot Studio integration.** This would be a skill in Microsoft 365 Copilot, not a standalone system. Enterprise value comes from integration with Teams, SharePoint, Outlook context.
- **Azure Active Directory for auth.** Not JWT + API keys. AAD OAuth2, role-based access, Conditional Access Policies, integration with enterprise identity providers.
- **Responsible AI tooling.** Azure Content Safety for input/output screening. Azure AI Fairness for bias monitoring. These are not optional in Microsoft's enterprise AI products.
- **Semantic Kernel instead of LangGraph.** Microsoft's own orchestration framework, deeply integrated with Azure services, with native support for memory plugins, planner, and step-by-step reasoning.

### Databricks Would Build It

Databricks approaches this as a **data engineering problem with AI on top**:

- **Delta Lake as the document store.** Version-controlled document corpus with time-travel. When a document changes, you can re-embed only changed chunks. You can roll back to a previous corpus state.
- **MLflow for the full ML lifecycle.** Model registry, experiment tracking, evaluation runs — all tracked in MLflow. Prompt changes are versioned experiments with metric comparisons.
- **Spark for ingestion at scale.** Distributed embedding of 100K documents is a Spark job. PySpark + Hugging Face transformers. Not a sequential Python loop.
- **Mosaic AI Vector Search.** Databricks' managed vector store with automatic embedding updates when source data changes. Full integration with Delta Lake.
- **Unity Catalog for governance.** Document access control enforced at the data catalog level, not the application level. Column-level security, row-level security, audit logging — all built in.

---

## TASK 4 — Retrieval Layer Redesign

### Current State Assessment

The current retrieval is RRF(dense, sparse) → cross-encoder rerank → top-k=5 fixed. This is **Phase 1** retrieval engineering. Here is the full progression to production-grade:

### Chunking: What's Wrong and What to Do

**Current problem:** Single chunking strategy for all document types.

**Production chunking architecture:**

```
Document → Type Detector → Strategy Router
    ├── PDF/Legal → Semantic Boundary Chunker (sentence-BERT boundaries)
    │     └── Parent-Child chunking: small child chunks (128t) + large parent (512t)
    │           Parent retrieved for context, child scored for precision
    ├── Code/Technical → AST-boundary chunker (never split inside functions)
    ├── Tables/CSV → Structured chunk (preserve column headers in every chunk)
    ├── Long narrative → Proposition chunker (convert sentences to propositions)
    │     └── "John Smith was born in 1990 in New York" → 
    │         ["John Smith was born in 1990", "John Smith was born in New York"]
    └── FAQ/KB → Q+A chunk pairs (question always in chunk metadata for BM25)
```

**Proposition chunking** (from the Dense X Retrieval paper) is the single most impactful improvement you can make. It converts documents from prose to atomic propositions that map cleanly to factual claims, dramatically improving claim-level grounding verification.

### Hybrid Search: What's Missing

**What RRF misses:**
- RRF only combines rank positions, not score magnitudes. A document ranked #1 with score 0.99 and one ranked #1 with score 0.51 get the same RRF contribution.
- No learned fusion weights. Your `dense_weight=0.7, sparse_weight=0.3` are arbitrary. These should be query-type-dependent learned parameters.

**Better architecture:**
```
Query Classifier (fast, small model)
    ├── Factual/Exact → Boost BM25 weight (0.6 sparse, 0.4 dense)
    ├── Semantic/Conceptual → Boost dense (0.2 sparse, 0.8 dense)
    ├── Named entity → Add entity linking + knowledge graph lookup
    └── Multi-hop → Decompose → iterative retrieval

Retrieval Ensemble:
    ├── Dense: text-embedding-3-large (3072d) with Matryoshka truncation to 256d for speed
    ├── Sparse: BM25+ (BM25Plus outperforms BM25 for short queries)
    ├── ColBERT: Late interaction retrieval — scores every token, much higher recall
    └── Keyword: Exact match for product codes, policy numbers, case citations

Fusion: LLM-Augmented Reranking (LARA) or RankGPT
    → Not just a cross-encoder — use an LLM to reason about relevance
    → Much higher precision but 2x cost
    → Use for top-5 selection from top-50 candidates
```

### Reranking: Current State vs Production

**Current:** `cross-encoder/ms-marco-MiniLM-L-6-v2` — a lightweight cross-encoder.

**Better options by trade-off:**

| Reranker | Latency | Quality | Cost |
|---|---|---|---|
| `ms-marco-MiniLM-L-6-v2` | 20ms | Baseline | Free |
| `ms-marco-MiniLM-L-12-v2` | 40ms | +8% | Free |
| `bge-reranker-large` | 80ms | +15% | Free |
| `Cohere Rerank v3` | 100ms API | +25% | $0.001/search |
| `RankGPT-4o-mini` | 500ms | +35% | $0.015/1K tokens |
| `Jina Reranker v2` | 60ms | +20% | Free |

**Recommendation:** `bge-reranker-large` locally. Cohere Rerank v3 for API-based. The jump from MiniLM-L-6 to bge-large is 15% precision improvement at 4x latency — worth it.

### Better Retrieval Evaluation

**Current:** None.

**Production retrieval evaluation:**
1. **NDCG@5, NDCG@10** — normalized discounted cumulative gain at k. Standard IR metric.
2. **MRR (Mean Reciprocal Rank)** — how early is the first relevant result?
3. **Recall@k** — what fraction of relevant documents appear in top-k?
4. **Context precision** — how many retrieved chunks are actually relevant?
5. **LLM-based retrieval judge** — GPT-4 evaluates if retrieved context is sufficient to answer the query.

Build a retrieval evaluation harness that runs weekly against a held-out question set with labeled relevant documents.

---

## TASK 5 — Hallucination Detection Redesign

### Current Architecture Failures

The current system is a 2-call LLM pipeline: extract claims → verify claims. This has fundamental problems:

1. **LLM extracting claims from LLM output** — the extractor and the generator can collude by learning the same "style." The extractor may fail to extract claims that the generator phrased ambiguously.

2. **LLM verifying claims against context** — prone to position bias (verifier pays more attention to claims near the top of context), sycophancy (verifier tends to mark claims as supported when the claim is confidently stated), and length bias.

3. **No calibration** — you don't know if your grounding score of 0.75 actually corresponds to 75% factual accuracy.

### State-of-the-Art Hallucination Prevention Framework

**Layer 0: Pre-Retrieval (Answerability Prediction)**
```
Before retrieval even starts:
  → Classify: Is this query answerable from the document corpus?
  → If no: Tell the user immediately, don't waste retrieval budget
  → Use a fast classifier trained on (query, corpus_summary) → answerable/not
```

**Layer 1: Retrieval Faithfulness Gate**
```
After retrieval, before generation:
  → Calculate max retrieval score
  → If max_score < 0.4: The corpus likely doesn't contain the answer
  → Flag: "Low-confidence retrieval" → different prompt that says "Based on limited information..."
  → Don't generate a confident answer from weak retrieval
```

**Layer 2: Constrained Generation**
```
Prompt engineering to minimize hallucination at source:
  → "Answer ONLY using information in the provided context"
  → "If the context does not contain sufficient information, say so explicitly"
  → "Do not infer beyond what is stated. Do not use prior knowledge."
  → Add: "Quote directly from the source when making specific claims"
```

**Layer 3: NLI-Based Claim Verification (Fast Path)**
```
Instead of LLM for verification:
  → Fine-tuned DeBERTa-v3-large on MNLI + custom RAG hallucination dataset
  → Input: (claim, supporting_passage) → ENTAILMENT / NEUTRAL / CONTRADICTION
  → 5ms per claim vs 500ms LLM call
  → 95% of claims verified this way
```

**Layer 4: LLM Judge for Ambiguous Cases**
```
When NLI confidence < 0.7:
  → Escalate to LLM judge (Claude Sonnet or GPT-4o-mini)
  → Structured prompt with explicit verdict options
  → Chain-of-thought reasoning required before verdict
  → Return: verdict + reasoning + supporting passage IDs
```

**Layer 5: Cross-Source Consistency Check**
```
If multiple sources are retrieved:
  → Check that sources don't contradict each other on key facts
  → If conflict detected: flag, apply majority vote, expose conflict in response
  → "Sources disagree on X: Source A says P, Source B says Q"
```

**Layer 6: Calibration & Threshold Tuning**
```
Monthly:
  → Sample 500 human-reviewed responses
  → Compute calibration curve: predicted confidence vs actual accuracy
  → Adjust GROUNDING_THRESHOLD per domain/query type
  → Expected Calibration Error (ECE) < 0.05 target
```

**The key insight Anthropic uses:** Hallucination detection should be **cheaper and faster than the original generation**. If your critic costs more than your generator, you've built a system that's too expensive to scale.

---

## TASK 6 — Self-Healing Mechanism Redesign

### Current Failure

The current healing system is:
1. Critic returns `is_hallucinated=True`
2. `healing_node` rewrites the query
3. Retrieve again
4. Repeat up to `max_retries=3`

This is **reactive retrieval retry**, not self-healing. True self-healing requires:
- Failure diagnosis (WHY did it fail?)
- Root cause identification (retrieval? generation? corpus gap?)
- Strategy selection (WHAT should change?)
- Learning (remember what worked for future similar failures)

### The Self-Healing Agent Architecture

```
Failure Detected
       │
       ▼
┌─────────────────────────────────────────────┐
│          DIAGNOSIS AGENT                     │
│                                              │
│  Inputs: query, chunks, answer, critic result│
│  Classifies failure into:                    │
│  ├── RETRIEVAL_MISS: Wrong chunks retrieved  │
│  ├── CORPUS_GAP: Answer not in corpus        │
│  ├── GENERATION_DRIFT: Model ignored context │
│  ├── AMBIGUOUS_QUERY: Query too vague        │
│  ├── CONFLICTING_SOURCES: Corpus inconsistent│
│  └── CONTEXT_OVERFLOW: Too much noise        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼ (failure_mode)
┌─────────────────────────────────────────────┐
│          STRATEGY SELECTOR                   │
│                                              │
│  RETRIEVAL_MISS → QueryDecomposer            │
│  CORPUS_GAP → WebSearchAugmenter            │
│  GENERATION_DRIFT → ConstrainedGeneration   │
│  AMBIGUOUS_QUERY → ClarificationAgent       │
│  CONFLICTING_SOURCES → ReconciliationAgent  │
│  CONTEXT_OVERFLOW → ContextPruner           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          RECOVERY EXECUTOR                   │
│                                              │
│  Executes selected strategy                  │
│  Records: (failure_mode, strategy, outcome)  │
│  Updates healing_success_rate per strategy   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          LEARNING AGENT                      │
│                                              │
│  Writes to healing_knowledge_base:           │
│  {query_pattern, failure_mode, strategy,     │
│   success_rate, avg_improvement}             │
│                                              │
│  Future similar queries: skip failed         │
│  strategies, start with proven ones          │
└─────────────────────────────────────────────┘
```

### The Four Healing Agents in Detail

**1. Healing Agent (Diagnosis)**
- Reads critic output, retrieval scores, query type
- Produces structured `FailureDiagnosis` with root cause
- Never a binary "hallucinated yes/no" — always a taxonomy

**2. Recovery Agent (Execution)**
- Receives strategy from Diagnosis
- Has a library of atomic recovery actions: query rewrite, k expansion, threshold drop, model upgrade, web search, context pruning
- Tracks which action it took for the Learning Agent

**3. Retry Agent (Orchestration)**
- Manages the retry budget (not just a counter — a token budget)
- Decides when diminishing returns warrant stopping vs continuing
- Detects oscillation, stuck states, and strategy exhaustion
- Has a "fast fail" mode for queries with < 10% chance of recovery

**4. Learning Agent (Memory)**
- Maintains a failure pattern database
- Clusters similar failures to detect systemic retrieval problems
- Surfaces: "15% of queries about Q3 financial data are failing — possible corpus gap"
- This is the difference between self-healing and self-improving

---

## TASK 7 — Agent Framework Comparison

### Deep Comparison

| Framework | Paradigm | Strengths | Weaknesses | Best For |
|---|---|---|---|---|
| **LangGraph** | State-machine | Explicit control flow, checkpointing, cycles, observability | Verbose, compiled graph hard to modify dynamically, LangChain ecosystem lock-in | Complex workflows with well-defined states and recovery requirements |
| **CrewAI** | Role-based collaboration | Easy to set up, role delegation, natural language task definition | Black-box orchestration, limited control, poor observability, not production-hardened | Rapid prototyping of collaborative multi-agent scenarios |
| **AutoGen** | Conversational agents | Microsoft-backed, good for code generation, GroupChat pattern | Unpredictable conversation length, hard to bound, limited state management | Code generation, research agents, exploratory tasks |
| **PydanticAI** | Type-safe, dependency injection | Excellent type safety, testability, DI pattern, no magic | Less ecosystem, limited community, no built-in graph support | Agents where correctness and testability are paramount |
| **OpenAI Agents SDK** | Tool-calling native | First-class OpenAI integration, Swarm pattern, simple | OpenAI-only, no open-source model support | OpenAI-native stacks, simple tool-use pipelines |
| **Custom Orchestration** | Full control | Maximum flexibility, no dependencies | Engineering cost, must solve all problems yourself | When you've outgrown all frameworks |

### Recommendation: Hybrid Architecture

**Do not pick one framework. Build a layered architecture:**

```
Layer 1: LangGraph (State Machine Orchestrator)
   → Controls the workflow graph
   → Handles state, checkpointing, and cycle detection
   → Your retry loops, healing state, quality gates

Layer 2: PydanticAI Agents (Individual Agent Logic)
   → Each agent (Retrieval, Generation, Critic, Healer) is a PydanticAI agent
   → Strong typing, DI, testable in isolation
   → Agents are called as tools from LangGraph nodes

Layer 3: OpenAI Agents SDK / LiteLLM (Model Abstraction)
   → Route to GPT-4o, Claude, Gemini, or local models
   → A/B model testing, cost routing, fallback chains
```

**Why not CrewAI:** You cannot have non-deterministic orchestration in a self-healing system. CrewAI's agents decide what to do next via LLM reasoning — this is incompatible with bounded retry loops and hard quality gates. You need deterministic control flow.

**Why not AutoGen:** The conversational paradigm means you cannot bound the number of LLM calls. A system that can spend 50 LLM calls to answer one question is not production-deployable.

---

## TASK 8 — Memory Redesign

### The Five Memory Tiers

#### Tier 1: Working Memory (Per-Request Lifespan)
```
Storage: LangGraph RAGState object (in-process)
Content: Current query, retrieved chunks, generation result, critic output, healing state
Retrieval: Direct field access
Lifecycle: Created at request start, destroyed at request end
Indexing: None (direct access)
Cost: ~0 (in-process)
```

**Missing from current design:** State size limits. Working memory must be bounded. A 3-cycle healing loop with 5 chunks per retrieval accumulates 15 chunks + 3 generations + 3 critic results in working memory. Define max sizes and eviction.

#### Tier 2: Session Memory (Per-Conversation Lifespan, Hours)
```
Storage: Redis Sorted Set (score = message timestamp)
Content: Last N turns of conversation (user queries + assistant answers)
Retrieval: ZRANGE by recency, O(log N)
Lifecycle: TTL 24h from last message
Indexing: By session_id (Redis key)
Cost: ~$0.001/GB/hour (Redis)
```

**Missing from current design:** Session memory should be COMPRESSED after 10 turns. Summarize old turns into a "session summary" rather than keeping full verbatim history. This reduces context window pressure while preserving long-term context.

#### Tier 3: Episodic Memory (Per-User Lifespan, Days-Weeks)
```
Storage: PostgreSQL + pgvector OR dedicated vector store with user namespace
Content: High-quality interactions (grounding_score > 0.8), user question patterns, domain interests
Retrieval: Semantic search (embedding similarity) + metadata filter by user_id
Lifecycle: 30-90 days, quality-weighted retention
Indexing: HNSW index on embedding, B-tree on user_id + timestamp
Cost: ~$0.10/user/month
```

**What's missing:** Episodic memory should inform retrieval strategy, not just prompt context. If a user repeatedly asks about regulatory compliance topics, retrieval should bias toward compliance documents even without explicit mention.

#### Tier 4: Semantic Memory (Domain Knowledge, Permanent)
```
Storage: Knowledge Graph (Neo4j / Amazon Neptune) + Vector Store
Content: Entity relationships, domain concepts, document ontology
Retrieval: Graph traversal + vector similarity hybrid
Lifecycle: Permanent (versioned with document corpus)
Indexing: Graph index + vector index
Cost: ~$500-2000/month (Neo4j cloud)
```

**This is the most under-developed tier.** Knowledge graph retrieval answers questions like:
- "What are all the subsidiaries of Company X?" (graph traversal)
- "Which documents mention entities related to John Smith's department?" (graph + vector)
- "How does Policy A relate to Regulation B?" (semantic relationship)

Vector search alone cannot answer these questions.

#### Tier 5: Procedural Memory (System Lifespan, Permanent)
```
Storage: PostgreSQL healing_knowledge_base table
Content: (failure_pattern, strategy, success_rate, improvement_delta)
Retrieval: Pattern matching + k-NN on failure embeddings
Lifecycle: Permanent, updated after each healing cycle
Indexing: B-tree on pattern_hash, vector index on failure_embedding
Cost: ~$10/month
```

**This is what turns self-healing into self-improving.** The system should get better at recovering from failures over time. Currently, every request is a fresh start with no institutional memory of what healing strategies worked.

---

## TASK 9 — Roadmap to Flagship Project

### Phase 1: Foundation Repair (2-3 weeks)
**Priority: Fix what's broken before adding anything new**

- **Fix chunk IDs** — deterministic SHA-256 content hash at ingestion
- **Add tenant isolation** — user_id scoping on all vector store operations
- **Replace SQLite with Postgres** — proper async SQLAlchemy + connection pooling
- **Add OpenTelemetry properly** — SDK spans in every node, W3C trace propagation
- **Add RAGAS** — real faithfulness/relevance metrics, not custom score
- **Add streaming API** — SSE endpoint with partial results
- **Move agents to DI** — no module-level singletons

**Deliverable:** A working system that doesn't have critical bugs  
**Complexity:** Medium  
**Resume Impact:** Low (this is table stakes)

---

### Phase 2: Retrieval Excellence (2-3 weeks)
**Priority: Best-in-class retrieval**

- **Proposition chunking** — implement Dense X Retrieval chunking strategy
- **Parent-child indexing** — small chunks for precision, large parents for context
- **ColBERT integration** — late interaction retrieval alongside dense + sparse
- **Adaptive k** — query-complexity-based k selection
- **Retrieval evaluation harness** — NDCG@k, MRR, Recall@k on labeled dataset
- **bge-reranker-large** — upgrade from MiniLM-L-6 to bge-large
- **Metadata filtering** — enforced at storage layer, not application layer

**Deliverable:** Retrieval evaluation showing quantitative improvement over baseline  
**Complexity:** High (requires labeled eval dataset construction)  
**Resume Impact:** HIGH — quantified retrieval metrics are rare in portfolios

---

### Phase 3: Hallucination Detection 2.0 (2-3 weeks)
**Priority: Production-grade critic**

- **Fine-tune DeBERTa-v3** on NLI + custom dataset for fast claim verification
- **Multi-granularity verification** — sentence → claim → paragraph hierarchy
- **Calibration framework** — monthly calibration curve analysis
- **Citation system** — every claim linked to specific chunk IDs with content snippets
- **Source conflict detection** — explicit cross-source consistency checking
- **Human-in-the-loop gates** — flag high-stakes low-confidence for human review
- **Conformal prediction** — set-based confidence intervals instead of point estimates

**Deliverable:** Critic accuracy benchmarked against human labels (>85% agreement)  
**Complexity:** Very High (requires labeled hallucination dataset)  
**Resume Impact:** VERY HIGH — fine-tuned NLI + calibrated confidence is genuinely impressive

---

### Phase 4: Multi-Agent Intelligence (3-4 weeks)
**Priority: Real multi-agent architecture**

- **Knowledge Graph integration** — Neo4j for entity relationships
- **Knowledge Graph RAG** — hybrid graph traversal + vector search
- **Specialized agent fleet:**
  - `PlannerAgent` — query decomposition into multi-hop retrieval plan
  - `SubQueryAgent` — parallel execution of sub-queries
  - `SynthesisAgent` — answer synthesis from sub-query results
  - `ConflictResolutionAgent` — principled handling of contradicting sources
  - `LearningAgent` — healing pattern database with strategy recommendations
- **Procedural memory** — healing knowledge base with pattern matching
- **Agent communication via typed protocols** — not free-form dict passing

**Deliverable:** Demo showing multi-hop question answering across 3+ document sources  
**Complexity:** Very High  
**Resume Impact:** VERY HIGH — multi-hop RAG with KG is frontier territory

---

### Phase 5: Enterprise & Observatory (2-3 weeks)
**Priority: Production-worthy enterprise features**

- **RBAC and document ACL** — document-level access control enforced at storage
- **Audit trail** — tamper-proof, append-only audit log (Postgres audit extension)
- **Active learning pipeline** — feedback → annotation → fine-tuning loop
- **Cost tracking** — per-request token accounting, cost attribution by user/team
- **Canary deployments** — 10% traffic split for model/prompt changes
- **Grafana dashboards** — quality metrics, retrieval quality, hallucination rate, cost
- **LangSmith full integration** — every LLM call traced and indexed
- **Load testing** — Locust/k6 test suite with SLO verification
- **Multi-model routing** — LiteLLM-based routing with cost and quality optimization

**Deliverable:** Enterprise-grade system with documented SLOs, cost model, security audit  
**Complexity:** Very High  
**Resume Impact:** HIGH — operational maturity separates projects from production systems

---

## TASK 10 — WOW Factor (Ranked by Impact)

### Rank 1: Knowledge Graph + Vector Hybrid RAG ⭐⭐⭐⭐⭐
**Why it stops recruiters:** Almost no portfolio project does this. Multi-hop reasoning over entity relationships is an active research area (KGRAG, HippoRAG). Implementing it means you understand the limitations of pure vector search and have built a solution.

**What to build:** Neo4j + LangGraph integration. Index entities and relationships from your document corpus. When a query contains named entities, execute graph traversal to find related entities, then retrieve chunks mentioning those entities.

**Demo:** "What are the tax implications for subsidiaries of companies that operate in both EU and US jurisdictions?" — answered by traversing a corporate structure graph, not brute-force vector search.

---

### Rank 2: Fine-Tuned NLI Critic with Calibrated Confidence ⭐⭐⭐⭐⭐
**Why it stops recruiters:** You trained a model. You evaluated it. You calibrated it. This is ML engineering, not prompt engineering. It demonstrates you can build real ML systems.

**What to build:** DeBERTa-v3-large fine-tuned on (claim, passage) → ENTAILMENT/CONTRADICTION. Train on FEVER + ANLI + custom dataset from your production logs. Evaluate on held-out set. Plot calibration curve.

---

### Rank 3: Autonomous Evaluation Agent with Active Learning ⭐⭐⭐⭐
**Why it stops recruiters:** Closing the feedback loop is what separates a demo from a production system. An agent that identifies its own weaknesses and flags them for improvement is genuinely novel.

**What to build:** An `AutoEvalAgent` that (1) identifies query clusters where it underperforms, (2) generates adversarial test cases for those clusters, (3) surfaces them to a human review queue, (4) ingests human labels back into the training pipeline.

---

### Rank 4: RL-Based Retrieval Parameter Optimization ⭐⭐⭐⭐
**Why it stops recruiters:** You're using reinforcement learning in production. Very few engineers have done this. The system gets measurably better over time with user interaction.

**What to build:** Frame retrieval as a bandit problem. Actions: {k, similarity_threshold, strategy_weights, reranker}. Reward: user feedback signal (implicit via session continuation, explicit via rating). Use Thompson Sampling or LinUCB to optimize retrieval parameters per query type.

---

### Rank 5: Multi-Modal RAG with Structured Table Extraction ⭐⭐⭐
**Why it stops recruiters:** Enterprise documents are full of tables, figures, charts. A RAG system that ignores them misses 40%+ of information in financial/legal documents.

**What to build:** Table extraction with Camelot/pdfplumber → structured JSON → LLM table summarizer → dual index (raw JSON for exact queries, text summary for semantic queries).

---

### Rank 6: MCP (Model Context Protocol) Integration ⭐⭐⭐
**Why it stops recruiters:** MCP is Anthropic's open standard that Claude and other models use for tool access. Building an MCP server that exposes your RAG system as a tool means Claude, Cursor, and other MCP clients can use your system. This is forward-thinking infrastructure thinking.

**What to build:** An MCP server exposing: `search_documents`, `get_document`, `verify_claim` as MCP tools. Any MCP client can now use your RAG system.

---

### Rank 7: Streaming Agent Swarm with Real-Time Progress ⭐⭐⭐
**Why it stops recruiters:** Users see agents working in real-time: "🔍 Retrieving... ✅ 5 chunks found | 🤔 Analyzing claims... ❌ Claim 3 unverified | 🔄 Healing: expanding search..." This is a demo that makes people lean forward.

**What to build:** SSE endpoint with agent status events. Each node emits typed events: `{type: "retrieval_start"}`, `{type: "chunks_found", count: 5}`, `{type: "claim_failed", claim: "..."}`. Frontend renders a live agent activity feed.

---

## TASK 11 — Final Production Blueprint

### Complete Folder Structure

```
self-healing-rag/
├── README.md                              # 🎯 Lead with demo GIF + architecture diagram
├── ARCHITECTURE.md                        # Deep technical decisions
├── pyproject.toml                         # uv/pip config, all deps
├── Makefile
├── docker-compose.yml
├── docker-compose.override.yml
├── .env.example
├── .pre-commit-config.yaml
│
├── backend/                               # Core Python application
│   ├── api/
│   │   ├── main.py                        # FastAPI app factory with lifespan
│   │   ├── middleware/
│   │   │   ├── auth.py                    # JWT RS256 + API key
│   │   │   ├── rate_limit.py              # Redis token bucket (Lua script, atomic)
│   │   │   ├── tenant.py                  # Tenant context injection
│   │   │   ├── tracing.py                 # OTel W3C propagation
│   │   │   └── error_handler.py
│   │   ├── routers/
│   │   │   ├── v1/
│   │   │   │   ├── query.py               # POST /v1/query, GET /v1/query/{id}
│   │   │   │   ├── query_stream.py        # GET /v1/query/{id}/stream (SSE)
│   │   │   │   ├── ingest.py
│   │   │   │   ├── feedback.py            # POST /v1/feedback (RLHF data)
│   │   │   │   ├── health.py
│   │   │   │   └── admin.py
│   │   └── schemas/v1/
│   │       ├── query.py
│   │       ├── ingest.py
│   │       └── feedback.py
│   │
│   ├── agents/
│   │   ├── base.py                        # BaseAgent with DI, tracing, cost tracking
│   │   ├── retrieval/
│   │   │   ├── agent.py
│   │   │   ├── chunkers/
│   │   │   │   ├── base.py
│   │   │   │   ├── proposition.py         # Dense X Retrieval proposition chunker
│   │   │   │   ├── semantic_boundary.py
│   │   │   │   ├── parent_child.py
│   │   │   │   └── ast_boundary.py        # Code-aware chunker
│   │   │   ├── embedders/
│   │   │   │   ├── base.py
│   │   │   │   ├── openai.py
│   │   │   │   ├── local.py
│   │   │   │   └── colbert.py             # Late-interaction embedder
│   │   │   ├── searchers/
│   │   │   │   ├── dense.py
│   │   │   │   ├── sparse.py              # BM25+
│   │   │   │   ├── colbert.py
│   │   │   │   ├── graph.py               # Knowledge graph retrieval
│   │   │   │   └── fusion.py              # Learned fusion weights by query type
│   │   │   ├── rerankers/
│   │   │   │   ├── cross_encoder.py       # bge-reranker-large
│   │   │   │   ├── cohere.py
│   │   │   │   └── rankgpt.py
│   │   │   └── adaptive.py                # Strategy selection based on query classifier
│   │   ├── generation/
│   │   │   ├── agent.py
│   │   │   ├── prompt_builder.py          # Context assembly + citation injection
│   │   │   ├── llm_router.py              # LiteLLM-based model routing
│   │   │   ├── cost_tracker.py            # Per-request token cost
│   │   │   └── token_manager.py
│   │   ├── critic/
│   │   │   ├── agent.py
│   │   │   ├── claim_extractor.py
│   │   │   ├── nli_verifier.py            # Fine-tuned DeBERTa NLI (fast path)
│   │   │   ├── llm_judge.py               # LLM judge for ambiguous cases
│   │   │   ├── citation_validator.py
│   │   │   ├── conflict_detector.py       # Cross-source consistency
│   │   │   ├── calibrator.py              # Confidence calibration
│   │   │   └── confidence_scorer.py
│   │   ├── healer/
│   │   │   ├── diagnosis_agent.py         # Root cause classification
│   │   │   ├── strategy_selector.py       # Knowledge-base-driven strategy selection
│   │   │   ├── recovery_agent.py          # Strategy execution
│   │   │   ├── learning_agent.py          # Healing pattern persistence
│   │   │   └── retry_controller.py        # Budget-aware orchestration
│   │   ├── planner/
│   │   │   ├── agent.py                   # Multi-hop query decomposition
│   │   │   ├── sub_query_executor.py      # Parallel sub-query execution
│   │   │   └── synthesis_agent.py         # Multi-source answer synthesis
│   │   ├── evaluation/
│   │   │   ├── agent.py                   # Offline evaluation orchestrator
│   │   │   ├── ragas_evaluator.py         # Real RAGAS integration
│   │   │   ├── retrieval_evaluator.py     # NDCG, MRR, Recall@k
│   │   │   ├── quality_gate.py
│   │   │   └── auto_eval_agent.py         # Autonomous weakness detection
│   │   └── memory_agents/
│   │       ├── session_agent.py
│   │       ├── episodic_agent.py
│   │       ├── knowledge_graph_agent.py
│   │       └── procedural_agent.py        # Healing pattern learner
│   │
│   ├── graph/
│   │   ├── state.py                       # RAGState with size limits
│   │   ├── nodes.py                       # DI-based nodes (no singletons)
│   │   ├── edges.py                       # 4-way routing (not binary)
│   │   ├── workflow.py                    # Graph with PostgresCheckpointer
│   │   └── runner.py                      # Async runner with timeout cascade
│   │
│   ├── core/
│   │   ├── config.py                      # Pydantic Settings v2
│   │   ├── logging.py                     # structlog JSON
│   │   ├── exceptions.py
│   │   ├── telemetry.py                   # OTel SDK bootstrap
│   │   ├── security.py                    # Input sanitization (model-based, not regex)
│   │   ├── pii_detector.py                # PII redaction before logging
│   │   └── cost_tracker.py
│   │
│   ├── memory/
│   │   ├── working.py                     # Bounded in-request state
│   │   ├── session.py                     # Redis + compression after N turns
│   │   ├── episodic.py                    # pgvector + user namespace isolation
│   │   ├── semantic.py                    # Knowledge graph layer
│   │   ├── procedural.py                  # Healing knowledge base
│   │   └── query_cache.py                 # Tenant-scoped semantic cache
│   │
│   ├── storage/
│   │   ├── vector/
│   │   │   ├── base.py
│   │   │   ├── chroma.py                  # With tenant namespace enforcement
│   │   │   ├── pinecone.py
│   │   │   └── pgvector.py                # For episodic memory
│   │   ├── graph/
│   │   │   ├── neo4j.py                   # Knowledge graph storage
│   │   │   └── entity_extractor.py
│   │   ├── relational/
│   │   │   ├── models.py                  # SQLAlchemy ORM
│   │   │   ├── repositories.py
│   │   │   ├── pool.py                    # Connection pool config
│   │   │   └── migrations/                # Alembic migrations
│   │   ├── cache/
│   │   │   └── redis.py                   # Lua script atomics
│   │   └── audit/
│   │       └── audit_log.py               # Append-only audit trail
│   │
│   ├── ingestion/
│   │   ├── loaders/
│   │   ├── chunkers/
│   │   ├── pipeline.py                    # Async pipeline with Celery worker
│   │   ├── deduplicator.py                # SHA-256 content hash
│   │   ├── validator.py                   # Document provenance + trust scoring
│   │   └── versioner.py                   # Document version tracking
│   │
│   ├── evaluation/                        # Offline evaluation (separate from serving)
│   │   ├── harness.py
│   │   ├── datasets/
│   │   ├── regression_gate.py
│   │   └── calibration.py
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── e2e/
│       ├── adversarial/
│       ├── load/                          # k6 scripts
│       └── fixtures/
│           ├── eval_dataset.jsonl         # 200+ QA pairs with ground truth
│           ├── adversarial_queries.jsonl  # Injection, hallucination triggers
│           └── retrieval_labeled.jsonl    # Labeled relevant docs per query
│
├── frontend/
│   ├── nextjs/                            # Production frontend (not Streamlit)
│   │   ├── src/
│   │   │   ├── app/
│   │   │   ├── components/
│   │   │   │   ├── AgentActivityFeed.tsx  # Live agent status stream
│   │   │   │   ├── CitationPanel.tsx      # Source citations with grounding status
│   │   │   │   ├── ConfidenceIndicator.tsx
│   │   │   │   └── HealingIndicator.tsx   # Shows when system self-healed
│   │   │   └── hooks/
│   │   │       └── useQueryStream.ts      # SSE hook for streaming
│   └── streamlit/                         # Dev/demo UI
│
├── mcp_server/                            # MCP server for Claude/Cursor integration
│   ├── server.py
│   └── tools/
│       ├── search.py                      # search_documents tool
│       ├── verify.py                      # verify_claim tool
│       └── ingest.py
│
├── ml/                                    # ML training pipelines
│   ├── nli_fine_tuning/
│   │   ├── train.py                       # DeBERTa fine-tuning
│   │   ├── dataset.py                     # FEVER + ANLI + custom data
│   │   └── evaluate.py
│   ├── retrieval_rl/
│   │   ├── bandit.py                      # Thompson Sampling for retrieval params
│   │   └── reward.py
│   └── active_learning/
│       ├── uncertainty_sampler.py
│       └── annotation_queue.py
│
├── infra/
│   ├── docker/
│   ├── kubernetes/
│   │   ├── base/
│   │   ├── overlays/
│   │   │   ├── staging/
│   │   │   └── production/
│   │   └── canary/                        # Argo Rollouts canary config
│   ├── terraform/                         # IaC for cloud resources
│   └── monitoring/
│       ├── prometheus/
│       ├── grafana/
│       │   └── dashboards/
│       │       ├── quality_health.json
│       │       ├── retrieval_quality.json
│       │       ├── cost_tracking.json
│       │       └── system_health.json
│       ├── alerting/
│       └── runbooks/                      # Operational runbooks
│
├── scripts/
│   ├── bootstrap.sh
│   ├── seed_documents.py
│   ├── run_eval.py
│   ├── calibrate_critic.py
│   └── run_load_test.sh
│
└── .github/
    └── workflows/
        ├── ci.yml
        ├── cd.yml
        ├── eval_regression.yml            # Runs on main merge only
        └── security_scan.yml             # Snyk, Bandit, pip-audit
```

---

### Deployment Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         CDN / WAF                                │
│              (CloudFlare / AWS CloudFront + WAF)                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                   Load Balancer (ALB/NLB)                        │
└──────┬────────────────────────────────────────┬──────────────────┘
       │                                        │
┌──────▼──────────────────────┐  ┌──────────────▼──────────────────┐
│   API Pods (3-20 replicas)   │  │   Worker Pods (Ingestion)        │
│   FastAPI + LangGraph        │  │   Celery + PDF processing        │
│   HPA: CPU + request queue   │  │   HPA: Queue depth               │
└──────┬──────────────────────┘  └──────────────────────────────────┘
       │
┌──────┼───────────────────────────────────────────────────────────┐
│      │            MANAGED SERVICES                               │
│  ┌───▼──────────────┐  ┌─────────────────────┐  ┌─────────────┐ │
│  │ Aurora Postgres   │  │ ElastiCache Redis    │  │ Pinecone /  │ │
│  │ (Multi-AZ)        │  │ (Cluster mode)       │  │ Weaviate    │ │
│  │ + Read Replica    │  │                      │  │ Cloud       │ │
│  └──────────────────┘  └─────────────────────┘  └─────────────┘ │
│                                                                   │
│  ┌──────────────────┐  ┌─────────────────────┐  ┌─────────────┐ │
│  │ Neo4j AuraDB      │  │ S3 (Document Store)  │  │ GPU Cluster │ │
│  │ (Knowledge Graph) │  │                      │  │ (Ollama /   │ │
│  │                   │  │                      │  │  vLLM)      │ │
│  └──────────────────┘  └─────────────────────┘  └─────────────┘ │
└───────────────────────────────────────────────────────────────────┘
       │
┌──────▼───────────────────────────────────────────────────────────┐
│                   OBSERVABILITY STACK                             │
│   Grafana Cloud / Datadog                                         │
│   ├── OTel Collector → Tempo (traces)                             │
│   ├── Prometheus → Grafana (metrics)                              │
│   ├── Loki (logs)                                                  │
│   └── LangSmith (LLM call traces)                                 │
└──────────────────────────────────────────────────────────────────┘
```

### CI/CD Architecture

```
PR Created
  → ruff + mypy (lint/type check)
  → pytest unit tests (< 30s)
  → docker build (validate image builds)
  → security scan (Bandit, pip-audit, Snyk)

Merged to Main
  → All PR checks
  → Integration tests (pytest against live Docker Compose)
  → Adversarial hallucination tests
  → Retrieval regression gate (NDCG@10 must not drop > 5%)
  → Evaluation regression gate (faithfulness, answer_relevance)
  → Build and push image to ECR
  → Deploy to staging
  → Smoke test staging

Deploy to Production (tag v*.*.*)
  → Canary: 10% traffic for 30 minutes
  → Monitor: hallucination_rate, p99_latency, error_rate
  → Auto-promote if metrics pass → roll to 100%
  → Auto-rollback if metrics degrade
```

---

## TASK 12 — Would This Genuinely Impress Senior AI Engineers?

### Current State: **No**

Here is the unfiltered truth:

**What the blueprint shows:** A staff engineer's thinking about system design. The vocabulary is right. The architectural patterns are correct in principle. The blueprint would pass a system design screen.

**What the code shows:** A junior-to-mid engineer's first LangGraph project. Global singletons. Binary hallucination detection. No actual RAGAS. No actual OpenTelemetry. SQLite in the project root. Chunk IDs generated at retrieval time. Memory with no tenant isolation.

**The gap between blueprint and implementation is the problem.** Senior engineers will clone the repo and run the code. The code doesn't match the document. That gap signals exactly what's missing: the ability to execute on complex architectural decisions.

### What Is Actually Missing for "Genuinely Impressive"

1. **Working end-to-end demo with real numbers.** Not "hallucination rate < 5%" as a claim — actual benchmark results from a real eval dataset with actual test cases. Numbers with methodology beat claims every time.

2. **One genuinely hard technical thing done well.** Pick ONE from: (a) fine-tuned NLI critic, (b) knowledge graph retrieval, (c) calibrated confidence, (d) RL-based retrieval optimization. Implement it completely. Benchmark it. Document the results. Going deep on one hard problem is more impressive than going shallow on ten.

3. **The code must match the blueprint.** A Staff engineer who reads your blueprint and then looks at your code will immediately notice: no PostgresCheckpointer, no OpenTelemetry, module-level singletons, SQLite in the root. These signal that the document was written after the code, aspirationally, not as a design that was implemented.

4. **Real evaluation data and methodology.** Create the `eval_dataset.jsonl` with 200 QA pairs. Run RAGAS. Show before/after numbers for self-healing. Show your NLI verifier accuracy vs a baseline prompt. Data-driven claims are what separate a real engineer from someone who watched YouTube tutorials.

5. **An architectural decision that shows genuine insight.** The chunking strategy, the calibration framework, the knowledge graph + vector hybrid, the RL bandit for retrieval — any one of these shows you've read the research and applied it. Right now, nothing in this codebase reflects current research (2023-2025).

### The Honest Benchmark

**Would it impress a recruiter who screens based on GitHub stars and README length?** Yes.

**Would it impress a hiring manager who asks technical questions about the code?** Currently, no — the code doesn't match the blueprint and has critical bugs.

**Would it impress a Staff Engineer peer-reviewer who reads the code?** Not yet — but it has the bones to get there in 4-6 weeks of focused work.

---

## Implementation Priority (What to Build First)

Follow this exact sequence:

1. **Fix chunk IDs** (2 hours) — SHA-256 hash at ingestion. Prerequisite for everything else.
2. **Remove all module-level singletons** (4 hours) — DI via FastAPI `Depends()`.
3. **Replace SQLite with Postgres** (4 hours) — add connection pooling, proper async SQLAlchemy.
4. **Add real OpenTelemetry** (1 day) — OTel SDK, spans in every node, trace propagation.
5. **Build `eval_dataset.jsonl`** (3-4 days) — 200 QA pairs with ground truth. This is the hardest thing. Do it anyway.
6. **Integrate RAGAS properly** (1 day) — offline, not in the serving path.
7. **Add tenant isolation** (1 day) — scope all vector operations by user_id.
8. **4-way critic routing** (4 hours) — FULLY_SUPPORTED / PARTIALLY / UNSUPPORTED / CONTRADICTED.
9. **PostgresCheckpointer** (4 hours) — add to graph compilation.
10. **Implement proposition chunker** (2 days) — research Dense X Retrieval, implement, evaluate.
11. **Build the evaluation harness** (3 days) — NDCG@k, MRR, Recall@k, regression gate in CI.
12. **Pick one WOW feature** — either KG RAG or fine-tuned NLI. Go all the way.

---

*Review completed. This project has excellent bones and a clear path to genuinely impressive. The gap between document and implementation must close. Fix the foundations before adding new features.*
