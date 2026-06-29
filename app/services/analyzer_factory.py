"""Factory for configured ticket analysis providers."""

from app.core.config import settings
from app.services.ai_provider_analysis import AIProviderTicketImpactAnalyzer
from app.services.analysis import TicketImpactAnalyzer


def get_configured_analyzer() -> TicketImpactAnalyzer:
    """Return the configured external AI analyzer."""
    if settings.effective_ai_provider == "mock" or not settings.effective_ai_api_key:
        raise RuntimeError("No hay IA configurada")
    return AIProviderTicketImpactAnalyzer()
