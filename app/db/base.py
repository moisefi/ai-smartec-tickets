"""SQLAlchemy declarative base."""

from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, mapped_column

created_at = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
updated_at = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
]


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }
