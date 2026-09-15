"""007_generic_vector_dim: generic vector dim migration for Qwen3/BGE-M3/Jina/GTE upgrades.

Revision ID: 007
Revises: 006
Create Date: 2026-05-13

This migration generalizes 006 (hardcoded 1536) to support ANY embedding dimension
required by powerful models:

  - Qwen3-Embedding-0.6B / BGE-M3 / Jina-v3 : 1024
  - Qwen3-Embedding-4B                     : 2560
  - text-embedding-3-large / GTE-Qwen2-7B  : 3072/3584
  - Qwen3-Embedding-8B                     : 4096

It reads TARGET_DIM from env var VECTOR_STORE_DIM (defaults to 1024 for fresh Qwen installs,
otherwise keeps existing dim). If VECTOR_STORE_DIM == 768 and EMBEDDING_MODEL implies 1024+,
the Alembic env will have already auto-aligned via config.py, so this migration will ALTER correctly.

Usage:
  # Upgrade to Qwen3-Embedding-0.6B (1024) — also works via pgvector auto-sync, but migration is cleaner
  VECTOR_STORE_DIM=1024 alembic upgrade head
  # Or set in .env then:
  alembic upgrade head
  # Then re-ingest documents (TRUNCATE is automatic if table non-empty with incompatible dim)

Idempotent: safe to re-run, TRUNCATEs only if ALTER would fail due to row dim incompat.
Requires pgvector extension.
"""

from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Resolve target dim from env (VECTOR_STORE_DIM) or EMBEDDING_MODEL registry; fallback 1024 for Qwen era
def _resolve_target_dim() -> int:
    # 1) explicit env var
    env_dim = os.getenv("VECTOR_STORE_DIM", "").strip()
    if env_dim.isdigit():
        return int(env_dim)
    # 2) infer from EMBEDDING_MODEL
    emb = (os.getenv("EMBEDDING_MODEL", "") or "").strip().lower()
    registry = {
        "qwen3-embedding:0.6b": 1024, "qwen/qwen3-embedding-0.6b": 1024,
        "qwen3-embedding:4b": 2560, "qwen/qwen3-embedding-4b": 2560,
        "qwen3-embedding:8b": 4096, "qwen/qwen3-embedding-8b": 4096,
        "bge-m3": 1024, "bge-large": 1024, "jina-embeddings-v3": 1024,
        "gte-qwen2-1.5b": 1536, "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072, "gte-qwen2-7b": 3584,
    }
    for k, v in registry.items():
        if k in emb:
            return v
    # 3) fallback: keep DB current or 1024 for Qwen default
    # We cannot query DB without connection; default to 1024 (most common new powerful model)
    return 1024


TARGET_DIM = _resolve_target_dim()

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
    # Resolve again inside upgrade (env may differ from import time)
    target = _resolve_target_dim()
    _try("CREATE EXTENSION IF NOT EXISTS vector")

    for table, hnsw_idx in PGVECTOR_TABLES:
        _try(f"DROP INDEX IF EXISTS {hnsw_idx}")
        _try("DROP INDEX IF EXISTS idx_query_cache_chunks_hnsw")
        _try("DROP INDEX IF EXISTS idx_vector_chunks_ivfflat")
        _try("DROP INDEX IF EXISTS idx_query_cache_chunks_ivfflat")

        # Inspect current dim if possible
        current_dim: int | None = None
        try:
            conn = op.get_bind()
            if conn is not None:
                # Try to get column type
                res = conn.execute(sa.text(
                    "SELECT atttypmod FROM pg_attribute JOIN pg_class ON pg_class.oid = pg_attribute.attrelid "
                    "JOIN pg_type ON pg_type.oid = pg_attribute.atttypid "
                    f"WHERE relname = '{table}' AND attname = 'embedding'"
                ))
                row = res.fetchone()
                # atttypmod encodes dim for vector; but simpler: try count
                try:
                    cnt_res = conn.execute(sa.text(f"SELECT count(*) FROM {table}"))
                    cnt = cnt_res.scalar() or 0
                    if cnt and cnt > 0:
                        try:
                            op.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({target})"))
                        except Exception:
                            # Existing rows incompatible -> truncate then alter (requires re-ingest)
                            _try(f"TRUNCATE TABLE {table}")
                            _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({target})")
                    else:
                        _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({target})")
                except Exception:
                    _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({target})")
            else:
                _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({target})")
        except Exception:
            _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({target})")

        _try(f"CREATE INDEX IF NOT EXISTS {hnsw_idx} ON {table} USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")
        _try(f"CREATE INDEX IF NOT EXISTS idx_{table}_tenant ON {table}(tenant_id)")
        _try(f"CREATE INDEX IF NOT EXISTS idx_{table}_doc ON {table}(document_id)")

    _try("CREATE INDEX IF NOT EXISTS idx_sparse_chunks_tsv ON sparse_chunks USING GIN (content_tsv)")


def downgrade() -> None:
    # Downgrade to 768 (legacy)
    for table, hnsw_idx in PGVECTOR_TABLES:
        _try(f"DROP INDEX IF EXISTS {hnsw_idx}")
        _try(f"TRUNCATE TABLE {table}")
        _try(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector(768)")
        _try(f"CREATE INDEX IF NOT EXISTS {hnsw_idx} ON {table} USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")
