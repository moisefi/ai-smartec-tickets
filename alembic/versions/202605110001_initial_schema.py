"""Initial schema.

Revision ID: 202605110001
Revises:
Create Date: 2026-05-11 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202605110001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial tables and PostgreSQL extensions."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    ticket_type = postgresql.ENUM(
        "nuevo_suministro",
        "ampliacion_potencia",
        "extension",
        "incidencia",
        "regulatorio",
        "otro",
        name="ticket_type",
        create_type=False,
    )
    ticket_status = postgresql.ENUM(
        "pendiente",
        "analizando",
        "estimado",
        "en_progreso",
        "qa",
        "cerrado",
        name="ticket_status",
        create_type=False,
    )
    ticket_priority = postgresql.ENUM(
        "baja",
        "media",
        "alta",
        "urgente",
        name="ticket_priority",
        create_type=False,
    )

    ticket_type.create(op.get_bind(), checkfirst=True)
    ticket_status.create(op.get_bind(), checkfirst=True)
    ticket_priority.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_companies_code"), "companies", ["code"], unique=True)
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=True)

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("type", ticket_type, nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tickets_id"), "tickets", ["id"], unique=False)
    op.create_index(op.f("ix_tickets_title"), "tickets", ["title"], unique=False)

    op.create_table(
        "ticket_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("complexity", sa.String(length=64), nullable=False),
        sa.Column("estimated_hours", sa.Integer(), nullable=False),
        sa.Column("affected_files", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("technical_summary", sa.Text(), nullable=False),
        sa.Column("recommended_tasks", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_analyses_id"), "ticket_analyses", ["id"], unique=False)
    op.create_index(op.f("ix_ticket_analyses_ticket_id"), "ticket_analyses", ["ticket_id"], unique=False)


def downgrade() -> None:
    """Drop initial tables and enum types."""
    op.drop_index(op.f("ix_ticket_analyses_ticket_id"), table_name="ticket_analyses")
    op.drop_index(op.f("ix_ticket_analyses_id"), table_name="ticket_analyses")
    op.drop_table("ticket_analyses")
    op.drop_index(op.f("ix_tickets_title"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_id"), table_name="tickets")
    op.drop_table("tickets")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_id"), table_name="companies")
    op.drop_index(op.f("ix_companies_code"), table_name="companies")
    op.drop_table("companies")
    op.execute("DROP TYPE IF EXISTS ticket_priority")
    op.execute("DROP TYPE IF EXISTS ticket_status")
    op.execute("DROP TYPE IF EXISTS ticket_type")
