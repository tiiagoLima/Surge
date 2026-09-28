"""MarketRadarUseCase — discovers market-wide drops, ignores holdings."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime

from src.investments.domain.models import Opportunity
from src.investments.domain.ports import (
    MarketAnalystPort,
    NotificationPort,
    PortfolioPort,
    QuotePort,
    StoragePort,
)

logger = logging.getLogger(__name__)


class MarketRadarUseCase:
    """Scans whole market via list_market_quotes (Brapi).

    Filters: drop >= threshold and ticker not in portfolio.

    Args:
        portfolio_port: To exclude owned tickers.
        market_quote_port: Must implement list_market_quotes() (Brapi).
        notification_port: Sends alerts.
        storage_port: Persists opportunities.
        drop_threshold_pct: Minimum drop %.
    """

    def __init__(
        self,
        portfolio_port: PortfolioPort,
        market_quote_port: QuotePort,
        notification_port: NotificationPort,
        storage_port: StoragePort,
        drop_threshold_pct: float = 5.0,
        analyst: MarketAnalystPort | None = None,
        max_opportunities: int | None = None,
    ) -> None:
        if drop_threshold_pct <= 0:
            raise ValueError("drop_threshold_pct must be > 0")
        if max_opportunities is not None and max_opportunities <= 0:
            raise ValueError("max_opportunities must be > 0")
        self._portfolio = portfolio_port
        self._market = market_quote_port
        self._notifier = notification_port
        self._storage = storage_port
        self._threshold = drop_threshold_pct
        self._analyst = analyst
        self._max_opportunities = max_opportunities

    @property
    def threshold(self) -> float:
        return self._threshold

    def execute(self) -> list[Opportunity]:
        """Discover market opportunities not in portfolio."""
        holdings_tickers = {h.ticker.upper() for h in self._portfolio.list_holdings()}
        # Also consider without .SA variant to avoid duplicates
        holdings_base = {t.replace(".SA", "") for t in holdings_tickers}

        quotes = self._market.list_market_quotes()
        if not quotes:
            logger.warning("MarketRadar: no market quotes returned")
            return []

        logger.info(
            "MarketRadar: %d market quotes, %d holdings excluded, threshold=%.1f%%",
            len(quotes),
            len(holdings_tickers),
            self._threshold,
        )

        now = datetime.now(UTC)
        opportunities: list[Opportunity] = []

        for quote in quotes:
            norm = quote.ticker.upper()
            base = norm.replace(".SA", "")
            if norm in holdings_tickers or base in holdings_base:
                continue
            if not quote.is_significant_drop(self._threshold):
                continue
            if (
                self._max_opportunities is not None
                and len(opportunities) >= self._max_opportunities
            ):
                continue
            drop = quote.drop_pct()
            assert drop is not None
            opp = Opportunity(
                quote=quote, drop_pct=drop, threshold_pct=self._threshold, detected_at=now
            )
            if self._analyst is not None:
                opp = replace(opp, insight=self._analyst.analyze(opp))
            opportunities.append(opp)
            try:
                self._storage.save_quote(quote)
                self._storage.save_opportunity(opp)
            except Exception:
                logger.exception("Failed to persist radar opp for %s", quote.ticker)
            logger.info("Opportunity (radar): %s", opp.summary())

        if opportunities:
            try:
                self._notifier.notify(opportunities)
            except Exception:
                logger.exception("Radar notification failed")
                try:
                    self._notifier.notify_error(
                        f"Surge radar: falha ao notificar {len(opportunities)} opps"
                    )
                except Exception:
                    logger.exception("notify_error failed")
        else:
            logger.info("MarketRadar complete — no opportunities")

        return opportunities
