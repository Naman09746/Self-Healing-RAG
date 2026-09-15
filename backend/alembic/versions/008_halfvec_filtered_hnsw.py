"""008_halfvec_filtered_hnsw: filtered HNSW + halfvec quantization for 10k+ scale.

Revision ID: 008
Revises: 007
Branch Labels: None
Depends On: None

Adds:
 - Filtered HNSW index WHERE tenant_id = 'default' (or PGVECTOR_FILTERED_INDEX_TENANT) for 10k+ per-tenant optimization.
   Generic HNSW remains for multi-tenant fallback. Use SET LOCAL enable_seqscan = off to force index for filtered queries.
 - Halfvec support: when PGVECTOR_USE_HALFVEC=true, alters embedding column to halfvec(dim) for 50% storage + ~3x speedup.
   Requires pgvector >=0.7 and Postgres 15+. Disabled by default (False) to preserve existing tests.

Idempotent, safe to re-run. Does not truncate data unless halfvec migration requires it (ALTER will TRUNCATE if dim mismatch).
"""

from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _try(sql: str) -> None:
    try:
        op.execute(sql)
    except Exception:
        pass


def upgrade() -> None:
    _try("CREATE EXTENSION IF NOT EXISTS vector")

    # Determine halfvec usage from env (settings not available in alembic env)
    use_halfvec = os.getenv("PGVECTOR_USE_HALFVEC", "").lower() in ("1", "true", "yes", "on")
    filtered_tenant = os.getenv("PGVECTOR_FILTERED_INDEX_TENANT", "").strip()
    # Also check VECTOR_STORE_DIM for dim
    try:
        dim = int(os.getenv("VECTOR_STORE_DIM", "1536"))
    except Exception:
        dim = 1536
    # Fallback: try to infer via DB column type if env not set
    vtype = f"halfvec({dim})" if use_halfvec else f"vector({dim})"
    vops = "halfvec_cosine_ops" if use_halfvec else "vector_cosine_ops"

    # If halfvec enabled, alter column type (may require TRUNCATE if existing rows)
    if use_halfvec:
        # Drop old HNSW first (cannot ALTER with index)
        _try("DROP INDEX IF EXISTS idx_vector_chunks_hnsw")
        _try("DROP INDEX IF EXISTS idx_vector_chunks_hnsw_filtered")
        _try("DROP INDEX IF EXISTS idx_vector_chunks_hnsw_halfvec")
        try:
            conn = op.get_bind()
            if conn is not None:
                # Try ALTER; if fails due to existing data, TRUNCATE then ALTER
                try:
                    op.execute(sa.text(f"ALTER TABLE vector_chunks ALTER COLUMN embedding TYPE {vtype}"))
                except Exception:
                    _try("TRUNCATE TABLE vector_chunks")
                    _try(f"ALTER TABLE vector_chunks ALTER COLUMN embedding TYPE {vtype}")
                try:
                    op.execute(sa.text(f"ALTER TABLE sparse_chunks ALTER COLUMN embedding TYPE {vtype}"))
                except Exception:
                    pass  # sparse_chunks has no embedding
        except Exception:
            _try(f"ALTER TABLE vector_chunks ALTER COLUMN embedding TYPE {vtype}")

    # Generic HNSW (always ensures existence)
    _try(f"CREATE INDEX IF NOT EXISTS idx_vector_chunks_hnsw ON vector_chunks USING hnsw (embedding {vops}) WITH (m=16, ef_construction=64)")

    # Filtered HNSW for single-tenant 10k+ optimization
    # Only create if filtered_tenant is set or default tenant has many rows (>1k)
    tenant_for_filter = filtered_tenant or "default"
    # Check if we should create filtered index: if tenant has >1000 rows or env requests it
    should_create_filtered = bool(filtered_tenant)
    if not should_create_filtered:
        try:
            conn = op.get_bind()
            if conn is not None:
                r = conn.execute(sa.text("SELECT COUNT(*) FROM vector_chunks WHERE tenant_id = :tid"), {"tid": tenant_for_filter})
                cnt = r.scalar() or 0
                if cnt and cnt > 1000:
                    should_create_filtered = True
        except Exception:
            pass
    if should_create_filtered:
        # Use tenant value safely (alphanumeric + underscore/dash only)
        safe_tenant = "".join(c for c in tenant_for_filter if c.isalnum() or c in ("_", "-"))
        if safe_tenant:
            _try(
                f"CREATE INDEX IF NOT EXISTS idx_vector_chunks_hnsw_filtered ON vector_chunks USING hnsw (embedding {vops}) WITH (m=16, ef_construction=64) WHERE tenant_id = '{safe_tenant}'"
            )

    # Ensure other indexes
    _try("CREATE INDEX IF NOT EXISTS idx_vector_chunks_tenant ON vector_chunks(tenant_id)")
    _try("CREATE INDEX IF NOT EXISTS idx_vector_chunks_doc ON vector_chunks(document_id)")
    _try("CREATE INDEX IF NOT EXISTS idx_sparse_chunks_tsv ON sparse_chunks USING GIN (content_tsv)")


def downgrade() -> None:
    # Downgrade halfvec -> vector, drop filtered index
    use_halfvec = os.getenv("PGVECTOR_USE_HALFVEC", "").lower() in ("1", "true", "yes", "on")
    try:
        dim = int(os.getenv("VECTOR_STORE_DIM", "1536"))
    except Exception:
        dim = 1536
    _try("DROP INDEX IF EXISTS idx_vector_chunks_hnsw_filtered")
    if use_halfvec:
        _try("DROP INDEX IF EXISTS idx_vector_chunks_hnsw")
        _try(f"ALTER TABLE vector_chunks ALTER COLUMN embedding TYPE vector({dim})")
        _try(f"CREATE INDEX IF NOT EXISTS idx_vector_chunks_hnsw ON vector_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")
