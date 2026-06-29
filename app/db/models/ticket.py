"""Ticket ORM model."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at

if TYPE_CHECKING:
    from app.db.models.company import Company
    from app.db.models.ticket_analysis import TicketAnalysis
    from app.db.models.user import User


class TicketType(enum.StrEnum):
    """Supported ticket types."""

    HISTORIA_USUARIO = "historia_usuario"
    TAREA = "tarea"
    INCIDENCIA = "incidencia"


class TicketStatus(enum.StrEnum):
    """Supported ticket statuses."""

    PENDIENTE = "pendiente"
    EN_CURSO = "en_curso"
    PRUEBAS_INTERNAS = "pruebas_internas"
    QA = "qa"
    DESPLEGADO = "desplegado"
    CIERRE = "cierre"


class TicketPriority(enum.StrEnum):
    """Supported ticket priorities."""

    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    URGENTE = "urgente"


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """Return enum values for SQLAlchemy persistence."""
    return [member.value for member in enum_class]


class Ticket(Base):
    """Technical ticket requested by a company."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[TicketType] = mapped_column(
        Enum(TicketType, name="ticket_type", values_callable=enum_values),
        nullable=False,
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status", values_callable=enum_values),
        default=TicketStatus.PENDIENTE,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority", values_callable=enum_values),
        nullable=False,
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    company: Mapped["Company"] = relationship(back_populates="tickets")
    assigned_user: Mapped["User | None"] = relationship(back_populates="tickets")
    analyses: Mapped[list["TicketAnalysis"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")
