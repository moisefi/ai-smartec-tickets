"""Application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI SmartEC Tickets"
    app_version: str = "0.1.0"
    environment: str = "local"

    postgres_user: str = "smartec"
    postgres_password: str = Field(default="smartec", repr=False)
    postgres_db: str = "ai_smartec_tickets"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    database_url: str | None = None
    test_database_url: str = "sqlite+aiosqlite:///:memory:"

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    auth_secret_key: str = Field(default="change-me-in-env", repr=False)
    access_token_expire_minutes: int = 480
    cors_origins: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]
    repository_cache_dir: str = "/tmp/ai_smartec_repositories"

    ai_provider: str = "mock"
    ai_api_key: str | None = Field(default=None, repr=False)
    ai_model: str = "gpt-4.1"
    ai_api_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: int = 90

    analysis_provider: str | None = None
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str | None = None
    openai_timeout_seconds: int | None = None

    @property
    def effective_ai_provider(self) -> str:
        """Return selected AI provider, supporting legacy ANALYSIS_PROVIDER."""
        return (self.analysis_provider or self.ai_provider).lower()

    @property
    def effective_ai_api_key(self) -> str | None:
        """Return provider API key, supporting legacy OPENAI_API_KEY."""
        return self.ai_api_key or self.openai_api_key

    @property
    def effective_ai_model(self) -> str:
        """Return selected AI model, supporting legacy OPENAI_MODEL."""
        return self.openai_model or self.ai_model

    @property
    def effective_ai_timeout_seconds(self) -> int:
        """Return AI request timeout."""
        return self.openai_timeout_seconds or self.ai_timeout_seconds

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the SQLAlchemy async database URL."""
        if self.database_url:
            return self.database_url
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def effective_celery_broker_url(self) -> str:
        """Return Celery broker URL."""
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_result_backend(self) -> str:
        """Return Celery result backend URL."""
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    """Build cached application settings."""
    return Settings()


settings = get_settings()
