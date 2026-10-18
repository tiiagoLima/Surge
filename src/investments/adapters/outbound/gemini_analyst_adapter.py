"""Gemini Analyst Adapter — uses Google Gemini API as the analytical brain."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from src.agent.adapters.outbound.provider_failure_classifier import classify_provider_exception
from src.agent.domain.provider_health import (
    ProviderHealth,
    ProviderHealthPort,
    ProviderHealthStatus,
)
from src.investments.domain.models import Opportunity
from src.investments.domain.ports import MarketAnalystPort

try:
    genai: Any = importlib.import_module("google.genai")
except ImportError:
    genai = None

logger = logging.getLogger(__name__)


class GeminiAnalystAdapter(MarketAnalystPort, ProviderHealthPort):
    """Analyzes market opportunities using Google Gemini.

    Implements MarketAnalystPort. Encapsulates the system prompt and
    gracefully degrades to a default string on any API failure.
    """

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash") -> None:
        """Initialize the adapter with a Gemini API key and model name.

        Args:
            api_key: The SURGE_GEMINI_API_KEY environment variable value.
            model: The Gemini model name (default: gemini-2.5-flash).
        """
        self._api_key = str(api_key).strip()
        self._model = model
        self._client: Any = None
        self._initialized = False
        self._health = ProviderHealth(
            "gemini",
            self._model,
            ProviderHealthStatus.DEGRADED if self._api_key else ProviderHealthStatus.UNAVAILABLE,
        )

    def get_health(self) -> ProviderHealth:
        """Return cached health without I/O."""
        return self._health

    def _record_failure(self, exc: Exception) -> None:
        failure = classify_provider_exception(exc, "gemini", self._model)
        self._health = ProviderHealth(
            "gemini",
            self._model,
            (
                ProviderHealthStatus.DEGRADED
                if failure.retryable
                else ProviderHealthStatus.UNAVAILABLE
            ),
            failure,
        )
        logger.warning("Gemini analyst: %s", failure.message)

    def check_health(self) -> ProviderHealth:
        """Explicitly probe model metadata without requesting analysis."""
        try:
            self._ensure_initialized()
            self._client.models.get(model=self._model)
        except Exception as exc:
            self._record_failure(exc)
        else:
            self._health = ProviderHealth("gemini", self._model, ProviderHealthStatus.AVAILABLE)
        return self._health

    def _ensure_initialized(self) -> None:
        if not self._api_key:
            raise ValueError("SURGE_GEMINI_API_KEY não configurada no ambiente.")
        if self._initialized:
            return
        if genai is None:
            raise RuntimeError("Biblioteca 'google-genai' não está disponível no ambiente.")
        self._client = genai.Client(api_key=self._api_key)
        self._initialized = True

    def analyze(self, opportunity: Opportunity) -> str:
        """Return a Gemini-generated insight about the given opportunity.

        The system prompt instructs the model to be concise (max 3 sentences),
        direct, and not give buy/sell recommendations.

        Returns:
            The model's response string, or a default fallback on any error.
        """
        try:
            self._ensure_initialized()
            if self._client is None:
                raise RuntimeError("Cliente do provedor indisponível.")

            ticker = opportunity.ticker
            prompt = (
                f"Você é o Surge, um assistente analítico. "
                f"Resuma os possíveis motivos da queda recente do ativo {ticker}. "
                f"Seja extremamente conciso (máximo de 3 frases), direto ao ponto, "
                f"e não dê recomendações de compra ou venda."
            )

            response = self._client.models.generate_content(model=self._model, contents=prompt)
            text = (response.text or "").strip()
            self._health = ProviderHealth("gemini", self._model, ProviderHealthStatus.AVAILABLE)
            if text:
                return text
            return "Insight indisponível devido a erro na API de análise."
        except Exception as exc:
            self._record_failure(exc)
            return "Insight indisponível devido a erro na API de análise."
