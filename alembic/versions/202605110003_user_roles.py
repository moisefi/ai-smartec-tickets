"""Add user roles for real login permissions.

Revision ID: 202605110003
Revises: 202605110002
Create Date: 2026-05-11 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605110003"
down_revision: str | None = "202605110002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add role column and mark admin/Sergio as admins."""
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'member')")
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("admin", "member", name="user_role"), nullable=False, server_default="member"),
    )
    op.execute("UPDATE users SET role = 'admin' WHERE username IN ('admin', 'Sergio')")
    op.alter_column("users", "role", server_default=None)


def downgrade() -> None:
    """Remove role column."""
    op.drop_column("users", "role")
    op.execute("DROP TYPE user_role")
