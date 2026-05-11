"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analysis, auth, companies, health, tickets, users
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application resources."""
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend MVP para gestion de tickets tecnicos electricos con analisis IA.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
app.include_router(analysis.router, prefix="/tickets", tags=["analysis"])
