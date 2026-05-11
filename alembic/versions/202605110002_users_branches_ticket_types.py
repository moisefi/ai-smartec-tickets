"""Users, company branches, and ticket type update.

Revision ID: 202605110002
Revises: 202605110001
Create Date: 2026-05-11 11:00:00.000000
"""

from collections.abc import Sequence
from hashlib import sha256

import sqlalchemy as sa

from alembic import op

revision: str = "202605110002"
down_revision: str | None = "202605110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


def upgrade() -> None:
    """Apply user management and ticket type changes."""
    op.add_column("companies", sa.Column("repo_branch", sa.String(length=255), nullable=True))

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "user_company_priorities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company_priority_user_company"),
        sa.UniqueConstraint("user_id", "priority_order", name="uq_user_company_priority_order"),
    )
    op.create_index(op.f("ix_user_company_priorities_company_id"), "user_company_priorities", ["company_id"])
    op.create_index(op.f("ix_user_company_priorities_id"), "user_company_priorities", ["id"])
    op.create_index(op.f("ix_user_company_priorities_user_id"), "user_company_priorities", ["user_id"])

    op.add_column("tickets", sa.Column("assigned_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tickets_assigned_user_id_users",
        "tickets",
        "users",
        ["assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "ticket_analyses",
        sa.Column("proposed_changes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.alter_column("ticket_analyses", "proposed_changes", server_default=None)

    op.execute("CREATE TYPE ticket_type_new AS ENUM ('historia_usuario', 'tarea', 'incidencia', 'bug')")
    op.execute(
        """
        ALTER TABLE tickets
        ALTER COLUMN type TYPE ticket_type_new
        USING (
            CASE
                WHEN type::text = 'incidencia' THEN 'incidencia'
                ELSE 'tarea'
            END
        )::ticket_type_new
        """
    )
    op.execute("DROP TYPE ticket_type")
    op.execute("ALTER TYPE ticket_type_new RENAME TO ticket_type")

    users_table = sa.table(
        "users",
        sa.column("username", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("full_name", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "username": "admin",
                "password_hash": _hash_password("admin"),
                "full_name": "Administrador",
                "is_active": True,
            },
            {
                "username": "Sergio",
                "password_hash": _hash_password("sergio"),
                "full_name": "Sergio",
                "is_active": True,
            },
            {
                "username": "Ignacio",
                "password_hash": _hash_password("ignacio"),
                "full_name": "Ignacio",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    """Revert user management and ticket type changes."""
    op.execute(
        """
        CREATE TYPE ticket_type_old AS ENUM (
            'nuevo_suministro',
            'ampliacion_potencia',
            'extension',
            'incidencia',
            'regulatorio',
            'otro'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE tickets
        ALTER COLUMN type TYPE ticket_type_old
        USING (
            CASE
                WHEN type::text = 'incidencia' THEN 'incidencia'
                ELSE 'otro'
            END
        )::ticket_type_old
        """
    )
    op.execute("DROP TYPE ticket_type")
    op.execute("ALTER TYPE ticket_type_old RENAME TO ticket_type")

    op.drop_column("ticket_analyses", "proposed_changes")
    op.drop_constraint("fk_tickets_assigned_user_id_users", "tickets", type_="foreignkey")
    op.drop_column("tickets", "assigned_user_id")
    op.drop_index(op.f("ix_user_company_priorities_user_id"), table_name="user_company_priorities")
    op.drop_index(op.f("ix_user_company_priorities_id"), table_name="user_company_priorities")
    op.drop_index(op.f("ix_user_company_priorities_company_id"), table_name="user_company_priorities")
    op.drop_table("user_company_priorities")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
    op.drop_column("companies", "repo_branch")
