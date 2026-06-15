"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-06-13 11:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_uuid", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("tenant_id", sa.String(), server_default=sa.text("'default'"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("document_id", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("user_uuid", sa.String(36), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True, index=True),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("query_text_hash", sa.String(64), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
    )

    # --- execution_traces ---
    op.create_table(
        "execution_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("session_id", sa.String(), nullable=True, index=True),
        sa.Column("query", sa.String(), nullable=True),
        sa.Column("phase", sa.String(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("is_error", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tokens_used", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )

    # --- evaluation_metrics ---
    op.create_table(
        "evaluation_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("session_id", sa.String(), nullable=True, index=True),
        sa.Column("grounding_score", sa.Float(), nullable=True),
        sa.Column("answer_relevance", sa.Float(), nullable=True),
        sa.Column("faithfulness", sa.Float(), nullable=True),
        sa.Column("retrieval_precision", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("evaluation_metrics")
    op.drop_table("execution_traces")
    op.drop_table("audit_logs")
    op.drop_table("documents")
    op.drop_table("users")