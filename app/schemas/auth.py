"""Authentication API schemas."""

from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """Payload used to start a user session."""

    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=3, max_length=128)


class LoginResponse(BaseModel):
    """Bearer token plus current user profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
