"""Replace ticket workflow statuses.

Revision ID: 202605110005
Revises: 202605110004
Create Date: 2026-05-11 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202605110005"
down_revision: str | None = "202605110004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Move existing tickets into the new workflow enum."""
    op.execute(
        """
        CREATE TYPE ticket_status_new AS ENUM (
            'pendiente',
            'en_curso',
            'pruebas_internas',
            'qa',
            'desplegado',
            'cierre'
        )
        """,
    )
    op.execute(
        """
        ALTER TABLE tickets
        ALTER COLUMN status TYPE ticket_status_new
        USING (
            CASE
                WHEN status::text IN ('analizando', 'estimado') THEN 'pendiente'
                WHEN status::text = 'en_progreso' THEN 'en_curso'
                WHEN status::text = 'qa' THEN 'qa'
                WHEN status::text = 'cerrado' THEN 'cierre'
                ELSE 'pendiente'
            END
        )::ticket_status_new
        """
    )
    op.execute("DROP TYPE ticket_status")
    op.execute("ALTER TYPE ticket_status_new RENAME TO ticket_status")


def downgrade() -> None:
    """Restore the previous workflow enum."""
    op.execute(
        """
        CREATE TYPE ticket_status_old AS ENUM (
            'pendiente',
            'analizando',
            'estimado',
            'en_progreso',
            'qa',
            'cerrado'
        )
        """,
    )
    op.execute(
        """
        ALTER TABLE tickets
        ALTER COLUMN status TYPE ticket_status_old
        USING (
            CASE
                WHEN status::text = 'en_curso' THEN 'en_progreso'
                WHEN status::text = 'pruebas_internas' THEN 'qa'
                WHEN status::text = 'desplegado' THEN 'qa'
                WHEN status::text = 'cierre' THEN 'cerrado'
                WHEN status::text = 'qa' THEN 'qa'
                ELSE 'pendiente'
            END
        )::ticket_status_old
        """
    )
    op.execute("DROP TYPE ticket_status")
    op.execute("ALTER TYPE ticket_status_old RENAME TO ticket_status")
