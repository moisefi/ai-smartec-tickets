"""Company API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    """Shared company fields."""

    name: str = Field(min_length=2, max_length=255, examples=["Iberdrola"])
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Z0-9_-]+$", examples=["IBE"])
    description: str | None = None
    repo_url: str | None = Field(default=None, max_length=500, examples=["https://github.com/org/repo.git"])
    repo_branch: str | None = Field(default=None, max_length=255, examples=["feature/iberdrola"])


class CompanyCreate(CompanyBase):
    """Payload to create a company."""


class CompanyUpdate(BaseModel):
    """Payload to update a company."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    code: str | None = Field(default=None, min_length=2, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    description: str | None = None
    repo_url: str | None = Field(default=None, max_length=500)
    repo_branch: str | None = Field(default=None, max_length=255)


class CompanyRead(CompanyBase):
    """Company response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
