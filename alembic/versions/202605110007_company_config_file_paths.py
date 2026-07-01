"""Add company config file paths.

Revision ID: 202605110007
Revises: 202605110006
Create Date: 2026-05-11 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605110007"
down_revision: str | None = "202605110006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add config paths used by repository-aware analysis."""
    op.add_column(
        "companies",
        sa.Column("config_file_paths", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.alter_column("companies", "config_file_paths", server_default=None)


def downgrade() -> None:
    """Remove company config paths."""
    op.drop_column("companies", "config_file_paths")
