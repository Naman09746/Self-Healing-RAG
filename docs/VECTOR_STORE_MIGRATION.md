# Vector Store Migration Guide

## Summary
The dense vector store is now **pluggable** via `VECTOR_STORE_PROVIDER`.

| Provider | When to use | Cost | Persistence |
|---|---|---|---|
| `chroma` (legacy) | Local dev, ephemeral demo | $0 | `./chroma_data` (loses data on Render) |
| `pgvector` **(recommended)** | Production, free-tier $0 | $0 — reuses existing Postgres (Neon) | Postgres ACID, backed up with DB |
| `qdrant` | >1M vectors or need <30ms p95 | Self-host $ or Cloud $$ | Rust HA |
| `pinecone` | Fully managed serverless | $$ per vector | Managed |

## Configuration

```bash
# .env or ConfigMap
VECTOR_STORE_PROVIDER=pgvector   # chroma | pgvector | qdrant | pinecone
VECTOR_STORE_DIM=768             # must match EMBEDDING_MODEL dim (nomic-embed-text=768)
PGVECTOR_EF_SEARCH=40
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=rag_collection
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=rag-collection
```

- `VECTOR_DUAL_WRITE=true` — writes to primary **and** Chroma for parity checks during migration.
- `VECTOR_LEGACY_FALLBACK=true` — query falls back to Chroma if primary fails.

## Migration Steps (Chroma → pgvector)

1. **Enable pgvector extension** (Neon dashboard → Enable `vector`, or `CREATE EXTENSION vector`)
2. **Run Alembic**
   ```bash
   alembic upgrade head  # creates 002_pgvector vector_chunks table
   ```
3. **Dry-run**
   ```bash
   python scripts/migrate_chroma_to_pgvector.py --dry-run --collection rag_collection
   ```
4. **Migrate**
   ```bash
   VECTOR_STORE_PROVIDER=pgvector python scripts/migrate_chroma_to_pgvector.py --verify-parity
   ```
5. **Dual-write verification (optional)**
   ```bash
   VECTOR_STORE_PROVIDER=pgvector VECTOR_DUAL_WRITE=true uvicorn backend.api.main:app
   # ingest a doc, then compare: python scripts/migrate_chroma_to_pgvector.py --verify-parity --sample-query "health check"
   ```
6. **Cutover**
   ```bash
   # Set in Render/ConfigMap
   VECTOR_STORE_PROVIDER=pgvector
   VECTOR_LEGACY_FALLBACK=false
   ```
7. **Decommission Chroma**
   ```bash
   docker compose --profile legacy down  # chroma no longer starts by default
   # After verification, delete ./chroma_data and infra/k8s/services/chroma.yaml
   ```

## Rollback

```bash
VECTOR_STORE_PROVIDER=chroma uvicorn backend.api.main:app
# or ConfigMap: VECTOR_STORE_PROVIDER=chroma
```

Chroma data remains in `./chroma_data` for one release when `VECTOR_DUAL_WRITE=true`.

## Qdrant / Pinecone Notes

- **Qdrant**: `docker compose --profile qdrant up -d` then `VECTOR_STORE_PROVIDER=qdrant`. Needs `QDRANT_URL`.
- **Pinecone**: Set `PINECONE_API_KEY`, index auto-created as serverless `cosine` if missing.

## Troubleshooting

- `vector type does not exist` → enable `vector` extension; check `SELECT * FROM pg_extension WHERE extname='vector'`
- `dim mismatch` → ensure `VECTOR_STORE_DIM` matches `EMBEDDING_MODEL` (nomic-embed-text=768, check Ollama `show nomic-embed-text`)
- `HNSW index not created` → falls back to `ivfflat` or seq scan; still correct but slower — create index manually after enabling extension
- `Pinecone 401` → rotate `PINECONE_API_KEY`, check `PINECONE_CLOUD/REGION`

## Architecture

All stores implement `VectorStore` protocol (`backend/storage/vector/base.py`) and return Chroma-compatible dicts for `HybridRetriever` RRF fusion. Embeddings via `backend/storage/vector/embeddings.py` (Ollama → OpenAI → hash fallback for tests).
