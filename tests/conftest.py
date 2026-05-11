"""Pytest fixtures."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory database session per test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        session.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("admin"),
                    full_name="Administrador",
                    role=UserRole.ADMIN,
                ),
                User(username="Sergio", password_hash=hash_password("sergio"), full_name="Sergio", role=UserRole.ADMIN),
                User(username="Ignacio", password_hash=hash_password("ignacio"), full_name="Ignacio"),
            ],
        )
        await session.commit()
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an HTTP client with database dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
