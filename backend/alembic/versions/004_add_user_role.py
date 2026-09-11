"""add_user_role

Revision ID: 004
Revises: 003
Create Date: 2026-09-11 11:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add role column to users table with default 'viewer'
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(),
            server_default=sa.text("'viewer'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
