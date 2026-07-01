"""Add ticket analysis required skill level.

Revision ID: 202605110008
Revises: 202605110007
Create Date: 2026-05-11 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605110008"
down_revision: str | None = "202605110007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add required skill level returned by analysis responses."""
    op.add_column(
        "ticket_analyses",
        sa.Column("required_skill_level", sa.String(length=32), nullable=False, server_default="mid"),
    )
    op.alter_column("ticket_analyses", "required_skill_level", server_default=None)


def downgrade() -> None:
    """Remove required skill level from analyses."""
    op.drop_column("ticket_analyses", "required_skill_level")
