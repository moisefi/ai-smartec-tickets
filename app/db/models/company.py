"""Company ORM model."""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at

if TYPE_CHECKING:
    from app.db.models.ticket import Ticket
    from app.db.models.user import UserCompanyPriority


class Company(Base):
    """Electric company using the ticketing platform."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    repo_url: Mapped[str | None] = mapped_column(String(500))
    repo_branch: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[created_at]

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    user_priorities: Mapped[list["UserCompanyPriority"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
