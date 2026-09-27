"""Composite QuotePort — tries primary, falls back to secondary."""

from __future__ import annotations

import logging

from src.investments.domain.models import Quote
from src.investments.domain.ports import QuotePort

logger = logging.getLogger(__name__)


class CompositeQuoteAdapter(QuotePort):
    """Tries primary QuotePort, falls back to secondary on None."""

    def __init__(self, primary: QuotePort, fallback: QuotePort) -> None:
        self._primary = primary
        self._fallback = fallback

    def get_quote(self, ticker: str) -> Quote | None:
        quote = self._primary.get_quote(ticker)
        if quote is not None:
            return quote
        logger.info("Primary quote failed for %s — trying fallback", ticker)
        return self._fallback.get_quote(ticker)

    def get_quotes(self, tickers: list[str]) -> list[Quote]:
        """Fetch quotes trying primary per-ticker, fallback if None."""
        results: list[Quote] = []
        for ticker in tickers:
            quote = self.get_quote(ticker)
            if quote is not None:
                results.append(quote)
        return results

    def list_market_quotes(self) -> list[Quote]:
        """Tries primary list_market_quotes; falls back to secondary if empty or fails."""
        try:
            quotes = self._primary.list_market_quotes()
            if quotes:
                return quotes
        except Exception:
            logger.exception("Primary list_market_quotes failed — trying fallback")

        logger.info("Primary market quotes empty or failed — trying fallback")
        try:
            return self._fallback.list_market_quotes()
        except Exception:
            logger.exception("Fallback list_market_quotes failed")
            return []
