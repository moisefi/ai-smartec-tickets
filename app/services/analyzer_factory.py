"""Factory for configured ticket analysis providers."""

from app.core.config import settings
from app.services.ai_provider_analysis import AIProviderTicketImpactAnalyzer
from app.services.analysis import MockTicketImpactAnalyzer, TicketImpactAnalyzer


def get_configured_analyzer() -> TicketImpactAnalyzer:
    """Return the configured analyzer, falling back to the local mock when needed."""
    if settings.effective_ai_provider != "mock" and settings.effective_ai_api_key:
        return AIProviderTicketImpactAnalyzer()
    return MockTicketImpactAnalyzer()
