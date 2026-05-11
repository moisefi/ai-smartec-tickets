"""Ticket analysis API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketAnalysisCreate(BaseModel):
    """Internal payload used to persist generated analysis."""

    ticket_id: int = Field(gt=0)
    complexity: str = Field(max_length=64)
    estimated_hours: int = Field(ge=1)
    affected_files: list[str]
    risks: list[str]
    technical_summary: str
    recommended_tasks: list[str]
    proposed_changes: list[dict[str, str]] = Field(default_factory=list)


class TicketAnalysisRead(BaseModel):
    """Ticket analysis response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    complexity: str
    estimated_hours: int
    affected_files: list[str]
    risks: list[str]
    technical_summary: str
    recommended_tasks: list[str]
    proposed_changes: list[dict[str, str]]
    created_at: datetime
