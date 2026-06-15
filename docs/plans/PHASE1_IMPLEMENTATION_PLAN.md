# Phase 1 Implementation Plan — Data Isolation & Deterministic Identifiers

## Scope
1. Tenant isolation in vector store operations (ChromaDB)
2. Tenant isolation in semantic query cache
3. Deterministic chunk IDs using SHA-256 content hashing
4. Storage-layer enforcement of tenant boundaries

## Tenant ID Strategy
Use `current_user.email` as the tenant identifier:
- Already available from JWT auth via `get_current_user()`
- Session IDs already prefixed with email (`query.py:33`)
- No org-level multi-tenancy needed for MVP
- Default tenant = `"default"` for backward compatibility with existing data

## Chunk ID Strategy
`sha256(f"{tenant_id}:{chunk_content}")[:32]` — Deterministic, includes tenant scope, no collisions across tenants, 32-char hex for reasonable storage.

---

## Files to Modify (12 files)

| # | File | Changes |
|---|------|---------|
| 1 | `backend/core/config.py` | Add `DEFAULT_TENANT_ID: str = "default"` |
| 2 | `backend/storage/db/models.py` | Add `tenant_id` column to User model |
| 3 | `backend/graph/state.py` | Add `tenant_id: str = ""` to RAGState |
| 4 | `backend/storage/vector/chroma.py` | Add `tenant_id` param to `add_chunks()`, `query()`, `delete_document()`; enforce `where` filters |
| 5 | `backend/memory/query_cache.py` | Add tenant-scoped collections or metadata filters |
| 6 | `backend/storage/retriever.py` | Thread `tenant_id` through to Chroma query |
| 7 | `backend/ingestion/pipeline.py` | Generate deterministic SHA-256 chunk IDs; pass tenant_id |
| 8 | `backend/graph/nodes.py` | Fix chunk_id generation (remove UUID4); thread tenant_id |
| 9 | `backend/graph/runner.py` | Accept and pass tenant_id |
| 10 | `backend/api/routers/query.py` | Derive tenant_id from auth context |
| 11 | `backend/api/routers/ingest.py` | Derive tenant_id from auth context |
| 12 | `backend/api/routers/auth.py` | Ensure tenant_id is accessible from DBUser |

## New Files (3 files)

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/storage/tenant.py` | Tenant isolation utilities (key construction, metadata helpers) |
| 2 | `tests/unit/test_tenant_isolation.py` | Unit tests for tenant filtering at storage layer |
| 3 | `tests/unit/test_deterministic_ids.py` | Unit tests for SHA-256 chunk ID generation |

## Implementation Order (dependency-aware)

```
Step 1: Config + Models + State     ← no dependencies
Step 2: Tenant utilities             ← depends on Step 1
Step 3: ChromaStore tenant isolation ← depends on Step 2
Step 4: QueryCache tenant isolation  ← depends on Step 2
Step 5: Deterministic chunk IDs      ← depends on Step 2
Step 6: Retriever tenant threading   ← depends on Step 3
Step 7: Graph nodes + runner         ← depends on Step 6
Step 8: API routers                  ← depends on Step 7
Step 9: Migration strategy doc       ← depends on all above
Step 10: Tests                       ← depends on all above
```

## Backward Compatibility
- Default tenant `"default"` used when no tenant_id specified
- Existing ChromaDB entries without tenant_id still retrievable via default tenant
- Query cache gets tenant-prefixed collection names; old `"query_cache"` collection used as fallback
- All existing API contracts preserved (tenant_id derived from auth, not new request fields)

## Data Migration Strategy
- **ChromaDB**: Script to read existing entries, add `tenant_id: "default"` to metadata, re-add
- **QueryCache**: Entries remain accessible via default tenant fallback; cache naturally expires
- **BM25**: Separate index per tenant on re-index; existing corpus readable as default tenant

## Rollback Strategy
Each file change is isolated. Rollback = revert changed files, keep new files. No destructive migrations.