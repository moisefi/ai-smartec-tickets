"""Ticket analysis ORM model."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at

if TYPE_CHECKING:
    from app.db.models.ticket import Ticket


class TicketAnalysis(Base):
    """AI-generated or mock technical impact analysis for a ticket."""

    __tablename__ = "ticket_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    complexity: Mapped[str] = mapped_column(String(64), nullable=False)
    required_skill_level: Mapped[str] = mapped_column(String(32), nullable=False, default="mid")
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    affected_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    risks: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    technical_summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_tasks: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    proposed_changes: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[created_at]

    ticket: Mapped["Ticket"] = relationship(back_populates="analyses")
