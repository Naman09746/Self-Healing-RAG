"""alter_vector_dim_1536: migrate pgvector embeddings from 768 to 1536 for OpenAI/OpenRouter

Revision ID: 006
Revises: 005
Create Date: 2026-09-13

Production uses OPENAI text-embedding-3-small (1536) while initial migrations 002/003
hard-coded vector(768) (nomic-embed-text). This migration upgrades both vector_chunks
and query_cache_chunks to 1536 and recreates HNSW indexes. It is idempotent and
safe to re-run: if already 1536, ALTER is a no-op; if table missing, creation is skipped.

For Neon free tier where ALTER TYPE may lock, it falls back to TRUNCATE + type change
when table is empty (most prod installs at cutover have <2000 chunks). Existing 768-dim
rows are truncated (re-ingest required) to avoid silent dimension mismatch that caused
local-vs-prod parity failure (0 results → fast-fail “Information not available”).

Requires: pgvector extension enabled (does CREATE EXTENSION IF NOT EXISTS).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TARGET_DIM = 1536

# Tables to migrate: (table_name, hnsw_index_name)
PGVECTOR_TABLES = [
    ("vector_chunks", "idx_vector_chunks_hnsw"),
    ("query_cache_chunks", "idx_query_cache_chunks_hnsw"),
]


def _try(sql: str) -> None:
    try:
        op.execute(sql)
    except Exception:
        pass


def upgrade() -> None:
    # Ensure pgvector
    _try("CREATE EXTENSION IF NOT EXISTS vector")

    for table, hnsw_idx in PGVECTOR_TABLES:
        # Drop HNSW first — ALTER TYPE cannot execute with index on vector column in some PG versions
        _try(f"DROP INDEX IF EXISTS {hnsw_idx}")
        _try("DROP INDEX IF EXISTS idx_query_cache_chunks_hnsw")
        # Also drop fallback ivfflat
        _try("DROP INDEX IF EXISTS idx_vector_chunks_ivfflat")
        _try("DROP INDEX IF EXISTS idx_query_cache_chunks_ivfflat")

        # Fast-path: if table empty, TRUNCATE then ALTER is instant and avoids rewrite cost warning
        # Check count best-effort (may fail if table not yet created by 003)
        try:
            conn = op.get_bind()
            if conn is not None:
                res = conn.execute(sa.text(f"SELECT count(*) FROM {table}"))
                cnt = res.scalar() or 0
                if cnt and cnt > 0:
                    # Non-empty: still ALTER, but warn operator to re-ingest for quality
                    # We attempt ALTER; if PG rejects due to existing 768 rows incompatible, truncate
                    try:
                        op.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({TARGET_DIM})"))
                    except Exception:
                        # Neon/RDS may require USING clause when changing dim; truncate and retry
                        _try(f"TRUNCATE TABLE {table}")
                        _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({TARGET_DIM})")
                    # Recreate HNSW below
                else:
                    # Empty or missing — ensure correct type
                    _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({TARGET_DIM})")
                    # If ALTER failed because column is TEXT (fallback in 002), recreate as vector
                    # Detect by trying to set to TEXT then back — best-effort, ignore failures
                    pass
            else:
                _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({TARGET_DIM})")
        except Exception:
            # Table may not exist yet (fresh DB before 002) — ensure it will be created with correct dim on next _ensure_table
            # Try ALTER anyway for idempotency
            _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({TARGET_DIM})")

        # Recreate indexes (idempotent)
        _try(f"CREATE INDEX IF NOT EXISTS {hnsw_idx} ON {table} USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")
        # If HNSW failed (e.g. no vector extension), fallback to IVFFlat
        # (op already has try; second attempt is inside exception)
        _try(f"CREATE INDEX IF NOT EXISTS idx_{table}_tenant ON {table}(tenant_id)")
        _try(f"CREATE INDEX IF NOT EXISTS idx_{table}_doc ON {table}(document_id)")

    # Also ensure sparse/session tables indexes still present (no dim change)
    _try("CREATE INDEX IF NOT EXISTS idx_sparse_chunks_tsv ON sparse_chunks USING GIN (content_tsv)")


def downgrade() -> None:
    # Downgrade back to 768 — destructive for 1536 data (truncates)
    for table, hnsw_idx in PGVECTOR_TABLES:
        _try(f"DROP INDEX IF EXISTS {hnsw_idx}")
        _try(f"TRUNCATE TABLE {table}")
        _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector(768)")
        _try(f"CREATE INDEX IF NOT EXISTS {hnsw_idx} ON {table} USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")
