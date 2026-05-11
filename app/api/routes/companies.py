"""Company CRUD routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.models.company import Company
from app.db.session import get_db
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter()


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(payload: CompanyCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> Company:
    """Create a company."""
    company = Company(**payload.model_dump())
    db.add(company)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company name or code already exists",
        ) from exc
    await db.refresh(company)
    return company


@router.get("", response_model=list[CompanyRead])
async def list_companies(db: Annotated[AsyncSession, Depends(get_db)]) -> list[Company]:
    """List companies."""
    result = await db.scalars(select(Company).order_by(Company.id))
    return list(result)


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Company:
    """Get a company by ID."""
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Company:
    """Update a company."""
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company name or code already exists",
        ) from exc
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[object, Depends(require_admin)],
) -> None:
    """Delete a company."""
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    await db.delete(company)
    await db.commit()
