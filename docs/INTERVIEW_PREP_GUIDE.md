# 🎯 Self-Healing RAG — Senior AI / System Design Interview Preparation Guide

**Document ID:** RAG-INTERVIEW-PREP-2026  
**Focus:** AI Systems Engineering, Multi-Agent Architecture, Vector Database Trade-offs & Production Latency Optimization  

---

## 📌 1. The 30-Second & 2-Minute Elevator Pitch

### ⚡ The 30-Second Punchy Pitch
> *"I designed and built **Self-Healing RAG**, a production-grade multi-agent knowledge system that detects hallucinations in real time and repairs them autonomously before serving responses. Unlike naive linear RAG pipelines that fail silently on missing context, this system pairs hybrid retrieval (pgvector + BM25 + Neo4j) with an adaptive Critic–Healer loop, cutting ungrounded claims while using knowledge-absence fast-fails and single-pass verifications to keep p95 latency under 1.5s."*

### 🎙️ The 2-Minute Technical Deep-Dive
> *"Standard RAG architectures suffer from three critical failure modes: silent retrieval misses, LLM hallucinations, and a lack of self-correcting feedback loops.
>
> In Self-Healing RAG, we solved this with a 7-agent state machine orchestrated via LangGraph:
> 1. **Intake & Planner:** Runs session history lookups in parallel with query complexity classification.
> 2. **Hybrid Multi-Modal Retrieval:** Fuses dense vector embeddings (pgvector HNSW), sparse keywords (BM25), and entity graphs (Neo4j) using Reciprocal Rank Fusion (RRF). If relevance scores fall below threshold, a **Knowledge-Absence Fast-Fail** exits in ~200ms without wasting expensive LLM generation tokens.
> 3. **Adaptive Critic:** For simple queries, it runs a single-pass verification; for complex queries, it extracts atomic claims and verifies them against ground truth chunks.
> 4. **Healer Loop:** If ungrounded or contradicted claims are found, a Healer agent rewrites the query and executes at most 1 targeted re-retrieval loop.
>
> We also migrated our vector layer from embedded ChromaDB to PostgreSQL `pgvector`, eliminating multi-worker SQLite lock contention, enabling true ACID consistency, and halving container memory footprint."*

---

## 🥊 2. High-Frequency Interview Questions & Master-Class Answers

### Q1: "Why did you migrate from ChromaDB to pgvector? Is it actually faster?"
**Strong Answer:**
> *"We didn't migrate solely for microsecond search speed — we migrated for **production reliability, multi-worker concurrency, and ACID transactions**.
>
> When running FastAPI with multiple Uvicorn worker processes in Docker/Kubernetes, embedded ChromaDB's SQLite layer suffered from `database is locked` file contention during concurrent document uploads. Each worker also loaded its own in-memory index, causing memory bloat. Furthermore, taking live backups of `./chroma_data` on disk risked corrupted index snapshots.
>
> With PostgreSQL `pgvector`:
> 1. We get **true ACID guarantees** and idempotent upserts (`ON CONFLICT DO UPDATE`).
> 2. Document metadata and embeddings reside in the same transactional boundary — zero orphaned vectors.
> 3. Multi-worker processes share an async SQLAlchemy connection pool with Postgres MVCC.
> 4. While embedded Chroma had a ~2–4ms in-memory lookup versus pgvector's ~6–15ms SQL roundtrip, that +6ms difference represents **less than 0.5%** of our total 1.5s pipeline latency (where LLM generation is ~950ms). We happily traded 6ms of raw lookup for 100% production reliability and standard `pg_dump` point-in-time recovery."*

---

### Q2: "Why use LangGraph over traditional linear chains (LangChain / LlamaIndex)?"
**Strong Answer:**
> *"Linear RAG pipelines are DAGs (Directed Acyclic Graphs) that execute strictly from step A to B. They cannot make runtime routing decisions, loop back upon failure, or manage dynamic state rollbacks.
>
> We used **LangGraph** because self-healing RAG is fundamentally a **cyclic state machine**:
> 1. **Cyclic Error Correction:** When the Critic flags an answer as `CONTRADICTED` or `PARTIALLY_SUPPORTED`, the edge condition routes back to the Healer and Retriever nodes, which is impossible in a linear chain.
> 2. **Bounded Retries:** LangGraph lets us strictly enforce loop invariants (e.g., `retry_count <= 1`) to prevent infinite token-burning loops.
> 3. **State Checkpointing & Resumption:** The central `RAGState` object maintains full history, claim audit trails, and execution checkpoints, enabling SSE streaming and asynchronous human-in-the-loop review."*

---

### Q3: "How do you detect hallucinations without exploding end-to-end latency?"
**Strong Answer:**
> *"Naive claim verification often triples latency because it makes multiple sequential LLM calls: one to extract claims, one to compare each claim against context, and one to grade the verdict.
>
> We solved this through an **Adaptive Latency Architecture**:
> 1. **Query Complexity Gate (<0.3 score):** Simple factoid queries bypass multi-step verification and use a **Single-Pass Batch Critic** (1 combined LLM prompt instead of 3).
> 2. **3-Stage Decomposition (Complex queries):** Only queries with multi-hop reasoning trigger atomic claim extraction and per-claim NLI verification (`SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`).
> 3. **Knowledge-Absence Fast-Fail (~200ms):** If retrieved context has a similarity score below our relevance floor, we skip the Generator and Critic completely, returning an honest 'No relevant knowledge found' response.
> 4. **Model Warmth (`keep_alive: 10m`):** We keep inference models resident in Ollama VRAM to eliminate 3–5s cold-start model swap overhead."*

---

### Q4: "Why use Hybrid Search (Dense + Sparse + Graph) instead of pure vector search?"
**Strong Answer:**
> *"Pure vector search fails on keyword-exact queries (like product IDs, error codes, or specialized acronyms) because semantic embeddings map them to generic neighborhood vectors. Conversely, BM25 keyword search fails on synonyms and conceptual paraphrasing.
>
> We combine:
> 1. **Dense Retrieval (`pgvector` HNSW):** Captures conceptual semantics and semantic intent.
> 2. **Sparse Retrieval (BM25):** Guarantees exact keyword and identifier matching.
> 3. **Graph Retrieval (Neo4j Cypher):** Traverses 1-to-N relationships and multi-hop entity connections that chunked text loses.
>
> We fuse all three ranking streams using **Reciprocal Rank Fusion (RRF, $k=60$)**, which normalizes disparate score distributions without requiring manual score weighting."*

---

### Q5: "How did you ensure multi-tenant isolation and prevent data leakage?"
**Strong Answer:**
> *"We enforce multi-tenancy at the **storage layer**, not just at the API boundary:
> 1. In `pgvector`, every chunk carries a `tenant_id`. Queries execute with a mandatory indexed predicate:
>    ```sql
>    SELECT ... FROM vector_chunks WHERE tenant_id = :tid ORDER BY embedding <=> :q_emb LIMIT :k;
>    ```
> 2. B-Tree index on `tenant_id` ensures Postgres filters out other tenants at index scan time before computing high-dimensional vector distances.
> 3. In the ingestion pipeline, the `enrich_metadata()` decorator automatically stamps the caller's JWT-extracted `tenant_id` onto chunks so developers cannot accidentally omit it."*

---

## 🏆 3. STAR Method Behavioral & Technical Stories

### Story 1: Concurrency Crash & Database Lock Resolution
- **Situation:** During multi-user load testing of the document upload endpoint with Uvicorn (4 workers), document ingestion crashed with `sqlite3.OperationalError: database is locked`.
- **Task:** Eliminate write concurrency bottlenecks and ensure 100% data consistency between relational document metadata and vector chunks.
- **Action:** Migrated the storage engine from embedded ChromaDB to PostgreSQL `pgvector`. Created an async SQLAlchemy session manager with pool size 5 / overflow 10, implemented idempotent SQL upserts with `ON CONFLICT (id) DO UPDATE`, and wrote an idempotent data migration script with hash-parity verification.
- **Result:** Successfully sustained 100+ concurrent ingestion requests with zero lock errors, reduced container RAM footprint by ~512MB, and unified all backups into standard Postgres WAL archiving.

### Story 2: Slashing 6-Second RAG Latency to <1.5s
- **Situation:** The initial multi-agent prototype took 5.8s on p95 queries due to sequential memory lookups, full 3-stage critique on every query, and cold LLM model reloads.
- **Task:** Reduce end-to-end response time under 1.5s while preserving hallucination detection accuracy.
- **Action:** Implemented 4 core optimizations:
  1. Parallelized session history and memory lookups via `asyncio.gather()`.
  2. Built an adaptive complexity classifier to route simple queries to a single-pass batch critic.
  3. Added a Knowledge-Absence Fast-Fail that aborts empty retrievals in ~200ms.
  4. Configured Ollama `keep_alive: 10m` to keep weights pinned in VRAM.
- **Result:** Dropped p95 latency by **74% (from 5.8s to 1.5s)** and cut LLM token consumption by 40% on unanswerable queries.

---

## 📊 4. System Latency & Architecture Numbers to Memorize

| Component / Step | Latency Budget | Technology / Implementation |
| :--- | :--- | :--- |
| **Intake & Memory** | ~15 ms | Redis async + `asyncio.gather()` |
| **Planner & Complexity** | ~80 ms | Heuristic 6-dimension regex classifier |
| **Dense Search** | ~9 ms | PostgreSQL `pgvector` HNSW index (`m=16, ef_search=40`) |
| **Sparse Search** | ~8 ms | In-memory BM25 index |
| **Graph Traversal** | ~25 ms | Neo4j Cypher query (3s hard timeout guard) |
| **RRF Fusion & Rerank**| ~65 ms | Cross-encoder reranker on top-15 candidates |
| **LLM Generation** | ~950 ms | Ollama (Llama 3.2:1b / Mistral 7b) with warm VRAM |
| **Adaptive Critic** | ~350 ms | Single-pass (fast-path) or 3-phase NLI verification |
| **Knowledge Fast-Fail**| **~200 ms** | Immediate early-exit when context relevance = 0 |
| **Total Pipeline p95** | **~1.50 s** | Full verified self-healing cycle |

---

## 💡 5. Tough Interviewer Traps & How to Handle Them

### ⚠️ Trap 1: *"If you have a Critic and a Healer, what prevents an infinite loop?"*
> **Answer:** *"The LangGraph state machine enforces a strict invariant: `retry_count <= MAX_RETRIES` (default `1`). If the second generation is still ungrounded, the system does not loop again; instead, it outputs the generated text accompanied by a low confidence score and an explicit verification warning banner to the user."*

### ⚠️ Trap 2: *"What if the Critic itself hallucinates that a valid claim is ungrounded?"*
> **Answer:** *"We use three safeguards:
> 1. **Temperature 0.0:** Deterministic inference for all verification prompts.
> 2. **Strict Structured JSON Schema:** The critic outputs exact claim-to-chunk span references.
> 3. **4-Way Routing:** Claims are not binary pass/fail; they are categorized into `FULLY_SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, and `CONTRADICTED`. Only `CONTRADICTED` triggers aggressive rewrites; `PARTIALLY_SUPPORTED` triggers a targeted minimal heal to preserve valid information."*

### ⚠️ Trap 3: *"Why not use a managed vector DB like Pinecone or Qdrant instead of pgvector?"*
> **Answer:** *"Our architecture actually uses a pluggable Factory pattern (`VECTOR_STORE_PROVIDER=pgvector|qdrant|pinecone|chroma`). However, for most enterprise deployments, `pgvector` is the optimal starting point because it minimizes distributed system complexity (no extra network hop to external SaaS, no dual-cloud security boundaries, zero additional cloud subscription costs) while handling up to millions of vectors efficiently with HNSW."*

---

## 📂 Quick Code Pointers to Reference

- **Vector Store Protocol & Implementation:** [`backend/storage/vector/pgvector.py`](file:///Users/namanjoshi/Workplace/Self-Healing-RAG/backend/storage/vector/pgvector.py)
- **Vector Factory & Pluggable Backends:** [`backend/storage/vector/factory.py`](file:///Users/namanjoshi/Workplace/Self-Healing-RAG/backend/storage/vector/factory.py)
- **LangGraph Multi-Agent State Machine:** [`backend/graph/workflow.py`](file:///Users/namanjoshi/Workplace/Self-Healing-RAG/backend/graph/workflow.py)
- **4-Way Routing Logic & Healing Loop:** [`backend/graph/edges.py`](file:///Users/namanjoshi/Workplace/Self-Healing-RAG/backend/graph/edges.py)
- **Complexity Classifier & Fast-Path Routing:** [`backend/graph/complexity.py`](file:///Users/namanjoshi/Workplace/Self-Healing-RAG/backend/graph/complexity.py)
- **Detailed Vector Store Benchmark Report:** [`docs/VECTOR_STORE_COMPARISON_REPORT.md`](file:///Users/namanjoshi/Workplace/Self-Healing-RAG/docs/VECTOR_STORE_COMPARISON_REPORT.md)
