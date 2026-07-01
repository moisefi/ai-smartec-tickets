"""Add user skill level.

Revision ID: 202605110006
Revises: 202605110005
Create Date: 2026-05-11 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605110006"
down_revision: str | None = "202605110005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add seniority level used by assignment and login responses."""
    op.execute("CREATE TYPE user_skill_level AS ENUM ('junior', 'mid', 'senior')")
    op.add_column(
        "users",
        sa.Column(
            "skill_level",
            sa.Enum("junior", "mid", "senior", name="user_skill_level"),
            nullable=False,
            server_default="mid",
        ),
    )
    op.execute("UPDATE users SET skill_level = 'senior' WHERE username IN ('admin', 'Sergio')")
    op.alter_column("users", "skill_level", server_default=None)


def downgrade() -> None:
    """Remove user seniority level."""
    op.drop_column("users", "skill_level")
    op.execute("DROP TYPE user_skill_level")
