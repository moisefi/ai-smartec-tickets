"""Reusable API dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.models.user import User, UserRole
from app.db.session import get_db


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Return the authenticated user from a bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_access_token(authorization.split(" ", maxsplit=1)[1])
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await db.get(User, int(payload["sub"]), options=[selectinload(User.company_priorities)])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Allow only admin users."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
