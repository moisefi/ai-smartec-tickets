"""User management routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.models.company import Company
from app.db.models.user import User, UserCompanyPriority
from app.db.session import get_db
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter()


async def get_user_or_404(db: AsyncSession, user_id: int) -> User:
    """Return a user or raise 404."""
    user = await db.get(User, user_id, options=[selectinload(User.company_priorities)])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def validate_company_priorities(db: AsyncSession, priorities: list[dict[str, int]]) -> None:
    """Validate priority payload before storing it."""
    company_ids = [priority["company_id"] for priority in priorities]
    priority_orders = [priority["priority_order"] for priority in priorities]
    if len(company_ids) != len(set(company_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company priorities cannot repeat companies",
        )
    if len(priority_orders) != len(set(priority_orders)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company priorities cannot repeat order")

    for company_id in company_ids:
        if await db.get(Company, company_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")


def apply_priorities(user: User, priorities: list[dict[str, int]]) -> None:
    """Replace user company priorities."""
    user.company_priorities.clear()
    user.company_priorities.extend(
        UserCompanyPriority(company_id=item["company_id"], priority_order=item["priority_order"])
        for item in priorities
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[object, Depends(require_admin)],
) -> User:
    """Create an internal user."""
    priority_data = [priority.model_dump() for priority in payload.company_priorities]
    await validate_company_priorities(db, priority_data)

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        skill_level=payload.skill_level,
        is_active=payload.is_active,
    )
    apply_priorities(user, priority_data)
    db.add(user)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc

    await db.refresh(user, attribute_names=["company_priorities"])
    return user


@router.get("", response_model=list[UserRead])
async def list_users(db: Annotated[AsyncSession, Depends(get_db)]) -> list[User]:
    """List internal users."""
    result = await db.scalars(
        select(User).options(selectinload(User.company_priorities)).order_by(User.id),
    )
    return list(result)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    """Get a user by ID."""
    return await get_user_or_404(db, user_id)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[object, Depends(require_admin)],
) -> User:
    """Update an internal user."""
    user = await get_user_or_404(db, user_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "company_priorities" in update_data and update_data["company_priorities"] is not None:
        priority_data = update_data.pop("company_priorities")
        await validate_company_priorities(db, priority_data)
        user.company_priorities.clear()
        await db.flush()
        apply_priorities(user, priority_data)

    if "password" in update_data and update_data["password"] is not None:
        user.password_hash = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc

    await db.refresh(user, attribute_names=["company_priorities"])
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[object, Depends(require_admin)],
) -> None:
    """Delete a user."""
    user = await get_user_or_404(db, user_id)
    await db.delete(user)
    await db.commit()
