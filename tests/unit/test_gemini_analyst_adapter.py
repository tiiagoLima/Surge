"""Unit tests for GeminiAnalystAdapter — using unittest.mock to avoid real network calls."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, r"C:\Surge")

from src.investments.adapters.outbound.gemini_analyst_adapter import (
    GeminiAnalystAdapter,  # type: ignore
)
from src.investments.domain.models import Opportunity, Quote  # type: ignore


def test_gemini_analyst_adapter_happy_path() -> None:
    """Test the happy path: Gemini returns a valid insight string."""
    api_key = "test-key-123"
    adapter = GeminiAnalystAdapter(api_key=api_key)

    quote = Quote(
        ticker="PETR4.SA",
        price=28.40,
        currency="BRL",
        timestamp=__import__("datetime").datetime(2026, 9, 27, 12, 0, 0),
        source="gemini",
    )
    opportunity = Opportunity(
        quote=quote,
        drop_pct=-7.5,
        threshold_pct=5.0,
        detected_at=__import__("datetime").datetime(2026, 9, 27, 12, 0, 0),
    )

    mock_response = MagicMock()
    mock_response.text = "Motivo: alta do dólar e queda de PETR4 no exterior."

    with patch("src.investments.adapters.outbound.gemini_analyst_adapter.genai") as mock_genai:
        instance = mock_genai.Client.return_value
        instance.models.generate_content.return_value = mock_response

        insight = adapter.analyze(opportunity)

    assert isinstance(insight, str)
    assert "PETR4" in insight
    assert "3 frases" not in insight  # concurrency check (implicit)
    # verify the model was called with the correct prompt
    instance.models.generate_content.assert_called_once()


def test_gemini_analyst_adapter_api_failure() -> None:
    """Test resiliency: any exception from Gemini returns the default fallback string."""
    api_key = "test-key-123"
    adapter = GeminiAnalystAdapter(api_key=api_key)

    quote = Quote(
        ticker="VALE3.SA",
        price=54.10,
        currency="BRL",
        timestamp=__import__("datetime").datetime(2026, 9, 27, 12, 0, 0),
        source="gemini",
    )
    opportunity = Opportunity(
        quote=quote,
        drop_pct=-3.2,
        threshold_pct=5.0,
        detected_at=__import__("datetime").datetime(2026, 9, 27, 12, 0, 0),
    )

    with patch("src.investments.adapters.outbound.gemini_analyst_adapter.genai") as mock_genai:
        instance = mock_genai.Client.return_value
        instance.models.generate_content.side_effect = RuntimeError("429 Too Many Requests")

        insight = adapter.analyze(opportunity)

    assert insight == "Insight indisponível devido a erro na API de análise."
