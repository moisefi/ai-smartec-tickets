"""Ticket analysis routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ticket import Ticket
from app.db.models.ticket_analysis import TicketAnalysis
from app.db.session import get_db
from app.schemas.analysis import TicketAnalysisRead
from app.services.analysis import TicketImpactAnalyzer
from app.services.analyzer_factory import get_configured_analyzer
from app.services.ticket_analysis_workflow import generate_and_store_analysis

router = APIRouter()


def get_analyzer() -> TicketImpactAnalyzer:
    """Return configured analyzer implementation."""
    return get_configured_analyzer()


@router.post("/{ticket_id}/analyze", response_model=TicketAnalysisRead, status_code=status.HTTP_201_CREATED)
async def analyze_ticket(
    ticket_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    analyzer: Annotated[TicketImpactAnalyzer, Depends(get_analyzer)],
) -> TicketAnalysis:
    """Analyze technical impact for a ticket and persist the result."""
    ticket = await db.get(Ticket, ticket_id, options=[selectinload(Ticket.company)])
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    try:
        analysis = await generate_and_store_analysis(db, ticket, analyzer)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(analysis)
    return analysis


@router.get("/{ticket_id}/analyses", response_model=list[TicketAnalysisRead])
async def list_ticket_analyses(ticket_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> list[TicketAnalysis]:
    """List analyses generated for a ticket."""
    if await db.get(Ticket, ticket_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    from sqlalchemy import select

    result = await db.scalars(
        select(TicketAnalysis).where(TicketAnalysis.ticket_id == ticket_id).order_by(TicketAnalysis.created_at.desc()),
    )
    return list(result)
