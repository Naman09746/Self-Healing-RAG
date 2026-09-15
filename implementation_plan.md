# Optimization Plan: Chunking, Vector Embeddings, and Hybrid Retrieval

Optimize the core ingestion and retrieval subsystems to maximize document fidelity, embedding throughput, and hybrid search precision.

## User Review Required

> [!IMPORTANT]
> All optimizations are backward-compatible with existing PostgreSQL pgvector schemas, deterministic chunk ID requirements, and tenant isolation rules.

---

## Proposed Changes

### 1. Document Chunking (`backend/ingestion/chunker.py`)
- **Markdown & Section Hierarchy Awareness**:
  - Introduce hierarchical boundary splitting (`# `, `## `, `### `, `#### `, `\n\n`, `\n`) to keep markdown sections, subsections, and lists cohesive.
  - Preserve markdown tables (`| ... |`) and code blocks (` ``` `) as atomic units without corrupting markdown syntax.
  - Normalize unicode whitespace and line endings prior to chunking.

### 2. Embedding Generation (`backend/storage/vector/embeddings.py`)
- **Query Embedding In-Memory Cache**:
  - Add thread-safe LRU caching (`lru_cache` on normalized text) for `embed_query` to eliminate redundant remote API calls on hot search terms.
- **Batched API Dispatching**:
  - Batch large chunk lists (up to 64 chunks per batch) in `_openai_embed` to optimize throughput and avoid payload timeouts.
- **Text Normalization**:
  - Trim and normalize input text before generating vector embeddings to prevent trailing whitespace distortions in vector space.

### 3. Hybrid Retrieval & Ranking (`backend/storage/retriever.py`)
- **Calibrated Reciprocal Rank Fusion (RRF)**:
  - Tune RRF with dense (pgvector) and sparse (tsvector / BM25) weight balancing.
  - Implement chunk content deduplication and Jaccard overlap filtering to eliminate redundant context chunks.
- **Strict Tenant & Quality Filtering**:
  - Preserve tenant isolation and clean candidate scoring.

---

## Verification Plan

### Automated Tests
```bash
pytest backend/tests/unit/test_chunker.py backend/tests/unit/test_chunker_edge_cases.py backend/tests/unit/test_pgvector_store.py backend/tests/integration/test_stream_endpoint.py
```

### Manual Verification
- Test chunking on sample markdown documents with headers, tables, and code blocks.
- Test query embedding cache and batched document ingestion.
- Run live query retrieval to verify high top-k context precision.
