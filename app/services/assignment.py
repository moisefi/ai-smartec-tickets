"""Ticket assignment services."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ticket import Ticket, TicketStatus
from app.db.models.user import User


async def auto_assign_user_id(db: AsyncSession, company_id: int) -> int | None:
    """Choose the best active user for a company.

    Users with an explicit company priority win first. Ties are resolved by lower open-ticket load.
    If no user has company priority, the active user with the lowest open-ticket load is selected.
    """
    users = list(
        await db.scalars(
            select(User)
            .where(User.is_active.is_(True))
            .options(selectinload(User.company_priorities))
            .order_by(User.id),
        ),
    )
    if not users:
        return None
    assignable_users = [user for user in users if user.username.lower() != "admin"] or users

    prioritized_users = [
        (
            user,
            min(priority.priority_order for priority in user.company_priorities if priority.company_id == company_id),
        )
        for user in assignable_users
        if any(priority.company_id == company_id for priority in user.company_priorities)
    ]

    candidates = sorted(prioritized_users, key=lambda item: item[1])
    candidate_users = [user for user, _ in candidates] or assignable_users

    loads = [(user.id, await _open_ticket_count(db, user.id)) for user in candidate_users]
    return min(loads, key=lambda item: item[1])[0]


async def _open_ticket_count(db: AsyncSession, user_id: int) -> int:
    """Count non-closed tickets assigned to a user."""
    return int(
        await db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.assigned_user_id == user_id,
                Ticket.status != TicketStatus.CIERRE,
            ),
        )
        or 0,
    )
