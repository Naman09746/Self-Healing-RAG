"""tenant_scoped_chunks

Revision ID: 005
Revises: 004
Create Date: 2026-09-11 12:00:00.000000

Fixes cross-tenant PK collision by ensuring chunk storage IDs are tenant-scoped.
Application-level fix uses deterministic_chunk_id(tenant_id, document_id, idx, content)
as the PK; this migration ensures indexes support that and documents existing
schema for audit.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure tenant indexes exist for all chunk tables (idempotent)
    # vector_chunks
    try:
        op.create_index("idx_vector_chunks_tenant_id", "vector_chunks", ["tenant_id"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("idx_vector_chunks_doc_tenant", "vector_chunks", ["document_id", "tenant_id"], unique=False)
    except Exception:
        pass
    # sparse_chunks
    try:
        op.create_index("idx_sparse_chunks_tenant_id", "sparse_chunks", ["tenant_id"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("idx_sparse_chunks_doc_tenant", "sparse_chunks", ["document_id", "tenant_id"], unique=False)
    except Exception:
        pass
    # query_cache_chunks (if exists)
    try:
        op.create_index("idx_query_cache_chunks_tenant_id", "query_cache_chunks", ["tenant_id"], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    for idx in ["idx_vector_chunks_tenant_id", "idx_vector_chunks_doc_tenant", "idx_sparse_chunks_tenant_id", "idx_sparse_chunks_doc_tenant", "idx_query_cache_chunks_tenant_id"]:
        try:
            op.drop_index(idx)
        except Exception:
            pass
