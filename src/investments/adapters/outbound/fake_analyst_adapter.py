"""Fake Analyst Adapter — used as fallback when Gemini API key is not configured."""

from __future__ import annotations

from src.investments.domain.models import Opportunity
from src.investments.domain.ports import MarketAnalystPort


class FakeAnalystAdapter(MarketAnalystPort):
    """Fakes a market analysis insight for testing and fallback scenarios."""

    def analyze(self, opportunity: Opportunity) -> str:  # type: ignore[override]
        return "Insight indisponível — adaptador de análise desativado."
