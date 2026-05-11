"""Ticket CRUD routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.models.company import Company
from app.db.models.ticket import Ticket
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.ticket import TicketCreate, TicketRead, TicketUpdate
from app.services.analyzer_factory import get_configured_analyzer
from app.services.assignment import auto_assign_user_id
from app.services.ticket_analysis_workflow import generate_and_store_analysis

router = APIRouter()


async def ensure_company_exists(db: AsyncSession, company_id: int) -> None:
    """Validate that a company exists."""
    if await db.get(Company, company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


async def ensure_user_exists(db: AsyncSession, user_id: int | None) -> None:
    """Validate that an assigned user exists when provided."""
    if user_id is not None and await db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: TicketCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> Ticket:
    """Create a ticket, auto-assign it, and generate its first impact analysis."""
    await ensure_company_exists(db, payload.company_id)
    await ensure_user_exists(db, payload.assigned_user_id)
    ticket_data = payload.model_dump()
    if ticket_data["assigned_user_id"] is None:
        ticket_data["assigned_user_id"] = await auto_assign_user_id(db, payload.company_id)

    if ticket_data["assigned_user_id"] is not None:
        assigned_user = await db.get(User, ticket_data["assigned_user_id"])
        ticket_data["assigned_to"] = assigned_user.username if assigned_user else None

    ticket = Ticket(**ticket_data)
    db.add(ticket)
    try:
        await db.flush()
        await db.refresh(ticket, attribute_names=["company"])
        await generate_and_store_analysis(db, ticket, get_configured_analyzer())
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket could not be created with the provided data",
        ) from exc
    except Exception:
        await db.rollback()
        raise
    await db.refresh(ticket)
    return ticket


@router.get("", response_model=list[TicketRead])
async def list_tickets(db: Annotated[AsyncSession, Depends(get_db)]) -> list[Ticket]:
    """List tickets."""
    result = await db.scalars(select(Ticket).order_by(Ticket.id))
    return list(result)


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(ticket_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Ticket:
    """Get a ticket by ID."""
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.put("/{ticket_id}", response_model=TicketRead)
async def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Ticket:
    """Update a ticket."""
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "company_id" in update_data:
        await ensure_company_exists(db, update_data["company_id"])
    if "assigned_user_id" in update_data:
        await ensure_user_exists(db, update_data["assigned_user_id"])

    for field, value in update_data.items():
        setattr(ticket, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket could not be updated with the provided data",
        ) from exc
    await db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[object, Depends(require_admin)],
) -> None:
    """Delete a ticket."""
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    await db.delete(ticket)
    await db.commit()
