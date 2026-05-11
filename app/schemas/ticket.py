"""Ticket API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.ticket import TicketPriority, TicketStatus, TicketType


class TicketBase(BaseModel):
    """Shared ticket fields."""

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=5)
    company_id: int = Field(gt=0)
    type: TicketType
    priority: TicketPriority
    assigned_to: str | None = Field(default=None, max_length=255)
    assigned_user_id: int | None = Field(default=None, gt=0)


class TicketCreate(TicketBase):
    """Payload to create a ticket."""

    status: TicketStatus = TicketStatus.PENDIENTE


class TicketUpdate(BaseModel):
    """Payload to update a ticket."""

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=5)
    company_id: int | None = Field(default=None, gt=0)
    type: TicketType | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: str | None = Field(default=None, max_length=255)
    assigned_user_id: int | None = Field(default=None, gt=0)


class TicketRead(TicketBase):
    """Ticket response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
