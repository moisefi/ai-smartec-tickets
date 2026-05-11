"""Ticket analysis persistence workflow."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ticket import Ticket
from app.db.models.ticket_analysis import TicketAnalysis
from app.services.analysis import TicketImpactAnalyzer


async def generate_and_store_analysis(
    db: AsyncSession,
    ticket: Ticket,
    analyzer: TicketImpactAnalyzer,
) -> TicketAnalysis:
    """Generate a ticket analysis, persist it, and update ticket status."""
    original_status = ticket.status
    await db.flush()

    generated = await analyzer.analyze(ticket)
    analysis = TicketAnalysis(
        ticket_id=ticket.id,
        complexity=generated.complexity,
        estimated_hours=generated.estimated_hours,
        affected_files=generated.affected_files,
        risks=generated.risks,
        technical_summary=generated.technical_summary,
        recommended_tasks=generated.recommended_tasks,
        proposed_changes=generated.proposed_changes,
    )
    ticket.status = original_status
    db.add(analysis)
    await db.flush()
    return analysis
