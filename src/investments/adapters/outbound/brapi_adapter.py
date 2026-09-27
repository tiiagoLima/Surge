"""BRAPI adapter — fallback QuotePort for B3 tickers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import requests

from src.investments.domain.models import Quote
from src.investments.domain.ports import QuotePort

logger = logging.getLogger(__name__)


class BrapiAdapter(QuotePort):
    """Fetches quotes via brapi.dev (good for B3)."""

    def __init__(
        self,
        base_url: str = "https://brapi.dev",
        token: str | None = None,
        timeout: int = 10,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def get_quote(self, ticker: str) -> Quote | None:
        # Normalize: brapi expects without .SA for B3, but accepts with
        clean = ticker.upper().replace(".SA", "")
        url = f"{self._base_url}/api/quote/{clean}"
        params: dict[str, str] = {}
        if self._token:
            params["token"] = self._token

        try:
            resp = requests.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if not results:
                logger.warning("brapi: no results for %s", ticker)
                return None
            r = results[0]
            price = r.get("regularMarketPrice")
            prev_close = r.get("regularMarketPreviousClose")
            currency = r.get("currency", "BRL")

            if price is None:
                return None

            return Quote(
                ticker=ticker.upper(),
                price=float(price),
                currency=str(currency).upper(),
                timestamp=datetime.now(UTC),
                source="brapi",
                previous_close=float(prev_close) if prev_close is not None else None,
            )
        except Exception:
            logger.exception("brapi error for %s", ticker)
            return None

    def list_market_quotes(self) -> list[Quote]:
        """Fetch market list via GET /api/quote/list (Brapi free)."""
        url = f"{self._base_url}/api/quote/list"
        params: dict[str, str] = {}
        if self._token:
            params["token"] = self._token
        try:
            resp = requests.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            stocks = data.get("stocks") or data.get("results") or []
            # Brapi list returns [{"stock":"PETR4","close":..., "change":..., ...}] or similar
            # Normalize to Quote objects where possible.
            quotes: list[Quote] = []
            for item in stocks:
                # Support two shapes: Brapi list has "stock"/"close" or detailed quote
                ticker = item.get("stock") or item.get("symbol") or item.get("ticker")
                if not ticker:
                    continue
                # Try to map price fields
                price = item.get("close") or item.get("regularMarketPrice") or item.get("price")
                prev_close = item.get("previousClose") or item.get("regularMarketPreviousClose")
                currency = item.get("currency", "BRL")
                change_pct = item.get("change")  # percent change
                # If price missing but change available, skip — need price for Quote
                if price is None:
                    continue
                # Derive previous_close from change if not provided
                if prev_close is None and change_pct is not None and price is not None:
                    try:
                        # change is percent, e.g. -5.2 means -5.2%
                        pct = float(change_pct)
                        if pct != -100:
                            prev_close = float(price) / (1 + pct / 100)
                    except Exception:
                        prev_close = None
                # Normalize ticker to B3 format with .SA
                norm_ticker = ticker.upper()
                if "." not in norm_ticker:
                    norm_ticker = f"{norm_ticker}.SA"
                quotes.append(
                    Quote(
                        ticker=norm_ticker,
                        price=float(price),
                        currency=str(currency).upper(),
                        timestamp=datetime.now(UTC),
                        source="brapi",
                        previous_close=float(prev_close) if prev_close is not None else None,
                    )
                )
            logger.info("brapi list_market_quotes: %d quotes", len(quotes))
            return quotes
        except Exception:
            logger.exception("brapi list_market_quotes failed")
            return []
