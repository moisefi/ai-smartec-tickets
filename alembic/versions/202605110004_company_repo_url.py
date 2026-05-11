"""Add repository URL to companies.

Revision ID: 202605110004
Revises: 202605110003
Create Date: 2026-05-11 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605110004"
down_revision: str | None = "202605110003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add repository URL and prefill Serisa when present."""
    op.add_column("companies", sa.Column("repo_url", sa.String(length=500), nullable=True))
    op.execute(
        """
        UPDATE companies
        SET repo_url = 'https://github.com/moisefi/Serisa_Control_Fichajes.git',
            repo_branch = 'master'
        WHERE lower(name) = 'serisa' OR upper(code) = 'SERISA'
        """
    )


def downgrade() -> None:
    """Remove repository URL."""
    op.drop_column("companies", "repo_url")
