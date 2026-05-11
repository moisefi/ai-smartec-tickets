"""User API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user import UserRole


class UserCompanyPriorityBase(BaseModel):
    """Shared user-company priority fields."""

    company_id: int = Field(gt=0)
    priority_order: int = Field(gt=0)


class UserCompanyPriorityCreate(UserCompanyPriorityBase):
    """Payload to assign company priority to a user."""


class UserCompanyPriorityRead(UserCompanyPriorityBase):
    """User-company priority response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


class UserBase(BaseModel):
    """Shared user fields."""

    username: str = Field(min_length=3, max_length=100)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.MEMBER
    is_active: bool = True


class UserCreate(UserBase):
    """Payload to create a user."""

    password: str = Field(min_length=3, max_length=128)
    company_priorities: list[UserCompanyPriorityCreate] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """Payload to update a user."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    password: str | None = Field(default=None, min_length=3, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    company_priorities: list[UserCompanyPriorityCreate] | None = None


class UserRead(UserBase):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    company_priorities: list[UserCompanyPriorityRead] = Field(default_factory=list)
