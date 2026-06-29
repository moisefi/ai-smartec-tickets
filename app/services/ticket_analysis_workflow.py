"""Ticket analysis persistence workflow."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ticket import Ticket
from app.db.models.ticket_analysis import TicketAnalysis
from app.db.models.user import User
from app.services.analysis import TicketImpactAnalyzer
from app.services.assignment import auto_assign_user_id


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
        required_skill_level=generated.required_skill_level,
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


async def assign_ticket_from_analysis(
    db: AsyncSession,
    ticket: Ticket,
    analysis: TicketAnalysis,
) -> None:
    """Assign an unanassigned ticket using AI-derived skill requirements."""
    if ticket.assigned_user_id is not None:
        return

    ticket.assigned_user_id = await auto_assign_user_id(db, ticket.company_id, analysis.complexity)
    if ticket.assigned_user_id is None:
        return

    assigned_user = await db.get(User, ticket.assigned_user_id)
    ticket.assigned_to = assigned_user.username if assigned_user else None
