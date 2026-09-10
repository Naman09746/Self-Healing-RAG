"""Free-tier: sessions + sparse tsvector tables

Revision ID: 003
Revises: 002
Create Date: 2026-09-10
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sessions table for PgSessionStore (free-tier, reuses Postgres)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS session_messages (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            expires_at TIMESTAMPTZ
        )
        """
    )
    try:
        op.create_index("idx_session_messages_session", "session_messages", ["session_id"])
    except Exception:
        pass
    try:
        op.create_index("idx_session_messages_expires", "session_messages", ["expires_at"])
    except Exception:
        pass

    # Sparse chunks for PgTsvectorSparseStore — generated tsvector if supported
    try:
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS sparse_chunks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
    except Exception:
        # Fallback without STORED generated column (older Postgres)
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS sparse_chunks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                content_tsv tsvector,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
    try:
        op.create_index("idx_sparse_chunks_tenant", "sparse_chunks", ["tenant_id"])
    except Exception:
        pass
    try:
        op.create_index("idx_sparse_chunks_doc", "sparse_chunks", ["document_id"])
    except Exception:
        pass
    try:
        op.execute("CREATE INDEX IF NOT EXISTS idx_sparse_chunks_tsv ON sparse_chunks USING GIN (content_tsv)")
    except Exception:
        pass

    # Ensure query_cache_chunks for pgvector QueryCache (avoid auto-create race)
    try:
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS query_cache_chunks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding vector(768),
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
    except Exception:
        # If vector not available, fallback to TEXT
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS query_cache_chunks (
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


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sparse_chunks_tsv")
    try:
        op.drop_index("idx_sparse_chunks_doc", table_name="sparse_chunks")
    except Exception:
        pass
    try:
        op.drop_index("idx_sparse_chunks_tenant", table_name="sparse_chunks")
    except Exception:
        pass
    op.execute("DROP TABLE IF EXISTS sparse_chunks")
    try:
        op.drop_index("idx_session_messages_expires", table_name="session_messages")
    except Exception:
        pass
    try:
        op.drop_index("idx_session_messages_session", table_name="session_messages")
    except Exception:
        pass
    op.execute("DROP TABLE IF EXISTS session_messages")
    op.execute("DROP TABLE IF EXISTS query_cache_chunks")
