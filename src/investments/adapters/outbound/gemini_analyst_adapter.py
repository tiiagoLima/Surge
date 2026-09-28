"""Gemini Analyst Adapter — uses Google Gemini API as the analytical brain."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from src.investments.domain.models import Opportunity
from src.investments.domain.ports import MarketAnalystPort

try:
    genai: Any = importlib.import_module("google.genai")
except ImportError:
    genai = None

logger = logging.getLogger(__name__)


class GeminiAnalystAdapter(MarketAnalystPort):
    """Analyzes market opportunities using Google Gemini.

    Implements MarketAnalystPort. Encapsulates the system prompt and
    gracefully degrades to a default string on any API failure.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the adapter with a Gemini API key.

        Args:
            api_key: The SURGE_GEMINI_API_KEY environment variable value.
        """
        self._api_key = api_key
        self._client: Any = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        if genai is None:
            return
        self._client = genai.Client(api_key=self._api_key)
        self._initialized = True

    def analyze(self, opportunity: Opportunity) -> str:
        """Return a Gemini-generated insight about the given opportunity.

        The system prompt instructs the model to be concise (max 3 sentences),
        direct, and not give buy/sell recommendations.

        Returns:
            The model's response string, or a default fallback on any error.
        """
        if not self._api_key:
            return "Insight indisponível devido a erro na API de análise."

        try:
            self._ensure_initialized()
            if self._client is None:
                return "Insight indisponível devido a erro na API de análise."

            ticker = opportunity.ticker
            prompt = (
                f"Você é o Surge, um assistente analítico. "
                f"Resuma os possíveis motivos da queda recente do ativo {ticker}. "
                f"Seja extremamente conciso (máximo de 3 frases), direto ao ponto, "
                f"e não dê recomendações de compra ou venda."
            )

            response = self._client.models.generate_content(
                model="gemini-3.8-flash", contents=prompt
            )
            text = (response.text or "").strip()
            if text:
                return text
            return "Insight indisponível devido a erro na API de análise."
        except Exception:
            logger.exception(
                "Gemini API call failed for ticker %s", getattr(opportunity, "ticker", "unknown")
            )
            return "Insight indisponível devido a erro na API de análise."
