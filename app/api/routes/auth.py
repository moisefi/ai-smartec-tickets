"""Authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> LoginResponse:
    """Authenticate a user and return a bearer token."""
    result = await db.scalars(
        select(User).where(User.username == payload.username).options(selectinload(User.company_priorities)),
    )
    user = result.first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role.value})
    return LoginResponse(access_token=token, user=user)
