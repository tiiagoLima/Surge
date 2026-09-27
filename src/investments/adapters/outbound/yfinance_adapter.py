"""YFinance adapter — primary QuotePort implementation."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime

import yfinance as yf

from src.investments.domain.models import Quote
from src.investments.domain.ports import QuotePort

logger = logging.getLogger(__name__)


class YFinanceAdapter(QuotePort):
    """Fetches quotes via yfinance. No business logic — just translation."""

    def get_quote(self, ticker: str) -> Quote | None:
        """Fetch latest quote for ticker.

        Returns None on failure (network, unknown ticker) instead of raising,
        so the UseCase can skip gracefully.
        """
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info  # fast_info is cheaper than history
            price = getattr(info, "last_price", None)
            prev_close = getattr(info, "previous_close", None)
            currency = getattr(info, "currency", None) or "USD"

            # Fallback to history if fast_info missing
            if price is None:
                hist = t.history(period="2d", auto_adjust=False)
                if hist.empty:
                    logger.warning("yfinance: no data for %s", ticker)
                    return None
                price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
                # Try currency from info dict
                with contextlib.suppress(Exception):
                    currency = t.info.get("currency", currency)  # type: ignore[union-attr]

            if price is None:
                return None

            return Quote(
                ticker=ticker.upper(),
                price=float(price),
                currency=str(currency).upper(),
                timestamp=datetime.now(UTC),
                source="yfinance",
                previous_close=float(prev_close) if prev_close is not None else None,
            )
        except Exception:
            logger.exception("yfinance error for %s", ticker)
            return None
