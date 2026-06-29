"""Ticket assignment services."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ticket import Ticket, TicketStatus
from app.db.models.user import User, UserSkillLevel

COMPLEXITY_SKILL_LEVELS = {
    "baja": [UserSkillLevel.JUNIOR, UserSkillLevel.MID],
    "media": [UserSkillLevel.MID, UserSkillLevel.SENIOR],
    "alta": [UserSkillLevel.SENIOR],
}


async def auto_assign_user_id(
    db: AsyncSession,
    company_id: int,
    complexity: str | None = None,
) -> int | None:
    """Choose the best active user for a company.

    Complexity decides the allowed skill levels. Company priority then wins, with ties
    resolved by lower open-ticket load.
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
    assignable_users = [user for user in users if user.username.lower() != "admin"]
    if not assignable_users:
        return None
    allowed_skill_levels = COMPLEXITY_SKILL_LEVELS.get((complexity or "").lower(), [UserSkillLevel.MID])
    candidate_pool = [user for user in assignable_users if user.skill_level in allowed_skill_levels]
    if not candidate_pool:
        return None

    prioritized_users = [
        (
            user,
            min(priority.priority_order for priority in user.company_priorities if priority.company_id == company_id),
        )
        for user in candidate_pool
        if any(priority.company_id == company_id for priority in user.company_priorities)
    ]

    candidates = sorted(prioritized_users, key=lambda item: item[1])
    candidate_users = [user for user, _ in candidates] or candidate_pool

    candidates_with_load = [
        (
            user.id,
            await _open_ticket_count(db, user.id),
            allowed_skill_levels.index(user.skill_level),
        )
        for user in candidate_users
    ]
    return min(candidates_with_load, key=lambda item: (item[1], item[2], item[0]))[0]


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
