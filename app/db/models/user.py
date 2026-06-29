"""User ORM models."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at
from app.db.models.ticket import enum_values

if TYPE_CHECKING:
    from app.db.models.company import Company
    from app.db.models.ticket import Ticket


class UserRole(enum.StrEnum):
    """Supported user roles."""

    ADMIN = "admin"
    MEMBER = "member"


class UserSkillLevel(enum.StrEnum):
    """Supported user seniority levels for ticket assignment."""

    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class User(Base):
    """Internal user that can own tickets and company priorities."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=enum_values),
        default=UserRole.MEMBER,
        nullable=False,
    )
    skill_level: Mapped[UserSkillLevel] = mapped_column(
        Enum(UserSkillLevel, name="user_skill_level", values_callable=enum_values),
        default=UserSkillLevel.MID,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[created_at]

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="assigned_user")
    company_priorities: Mapped[list["UserCompanyPriority"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserCompanyPriority(Base):
    """Priority order of companies assigned to a user."""

    __tablename__ = "user_company_priorities"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company_priority_user_company"),
        UniqueConstraint("user_id", "priority_order", name="uq_user_company_priority_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped["User"] = relationship(back_populates="company_priorities")
    company: Mapped["Company"] = relationship(back_populates="user_priorities")
