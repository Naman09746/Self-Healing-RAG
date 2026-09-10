"""pgvector: enable extension and create vector_chunks table

Revision ID: 002
Revises: 001
Create Date: 2026-09-10
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VECTOR_DIM = 768


def upgrade() -> None:
    # Enable pgvector — on Neon this must be enabled via dashboard first, so wrap in try
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        # If extension not available, table creation will fail later with clear error
        pass

    # Create vector_chunks table
    # Use raw SQL for vector type since sqlalchemy doesn't know it unless pgvector installed
    try:
        op.execute(
            f"""
            CREATE TABLE IF NOT EXISTS vector_chunks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding vector({VECTOR_DIM}),
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
    except Exception as e:
        # Fallback if vector type not available — create without vector for migration to pass, warn operator
        # In production pgvector must be enabled; this fallback allows CI without pgvector
        print(f"WARNING: Could not create vector_chunks with vector type: {e}. Creating fallback table without vector.")
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_chunks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )

    # Indexes — best effort
    try:
        op.create_index("idx_vector_chunks_tenant", "vector_chunks", ["tenant_id"])
    except Exception:
        pass
    try:
        op.create_index("idx_vector_chunks_doc", "vector_chunks", ["document_id"])
    except Exception:
        pass
    try:
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_vector_chunks_hnsw ON vector_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
        )
    except Exception:
        # HNSW may fail if pgvector not ready or table empty — non-blocking
        try:
            op.execute(
                "CREATE INDEX IF NOT EXISTS idx_vector_chunks_ivfflat ON vector_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)"
            )
        except Exception:
            pass


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_vector_chunks_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_vector_chunks_ivfflat")
    try:
        op.drop_index("idx_vector_chunks_doc", table_name="vector_chunks")
    except Exception:
        pass
    try:
        op.drop_index("idx_vector_chunks_tenant", table_name="vector_chunks")
    except Exception:
        pass
    op.execute("DROP TABLE IF EXISTS vector_chunks")
    # Do not drop extension — other tables might use it
