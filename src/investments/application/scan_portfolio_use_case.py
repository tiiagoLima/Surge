"""ScanPortfolioUseCase — monitors user's holdings."""

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


class ScanPortfolioUseCase:
    """Scans portfolio holdings for significant drops.

    Args:
        portfolio_port: Source of tickers (holdings).
        quote_port: Fetches quotes (Composite YFinance->Brapi).
        notification_port: Sends alerts.
        storage_port: Persists quotes/opportunities.
        drop_threshold_pct: Minimum drop % to trigger.
    """

    def __init__(
        self,
        portfolio_port: PortfolioPort,
        quote_port: QuotePort,
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
        self._quotes = quote_port
        self._notifier = notification_port
        self._storage = storage_port
        self._threshold = drop_threshold_pct
        self._analyst = analyst
        self._max_opportunities = max_opportunities

    @property
    def threshold(self) -> float:
        return self._threshold

    def execute(self) -> list[Opportunity]:
        """Scan all holdings. Returns opportunities."""
        holdings = self._portfolio.list_holdings()
        if not holdings:
            logger.info("ScanPortfolio: carteira vazia")
            return []

        tickers = [h.ticker for h in holdings]
        logger.info("ScanPortfolio: %d holdings, threshold=%.1f%%", len(tickers), self._threshold)

        opportunities: list[Opportunity] = []
        now = datetime.now(UTC)

        holdings_by_ticker = {holding.ticker.upper(): holding for holding in holdings}

        for ticker in tickers:
            quote = self._quotes.get_quote(ticker)
            if quote is None:
                logger.warning("No quote for %s — skipping", ticker)
                continue
            try:
                self._storage.save_quote(quote)
            except Exception:
                logger.exception("Failed to save quote for %s", ticker)

            if quote.is_significant_drop(self._threshold):
                if (
                    self._max_opportunities is not None
                    and len(opportunities) >= self._max_opportunities
                ):
                    continue
                drop = quote.drop_pct()
                assert drop is not None
                holding = holdings_by_ticker.get(ticker.upper())
                opp = Opportunity(
                    quote=quote,
                    drop_pct=drop,
                    threshold_pct=self._threshold,
                    detected_at=now,
                    holding=holding,
                )
                if self._analyst is not None:
                    opp = replace(opp, insight=self._analyst.analyze(opp))
                opportunities.append(opp)
                try:
                    self._storage.save_opportunity(opp)
                except Exception:
                    logger.exception("Failed to save opportunity for %s", ticker)
                logger.info("Opportunity (portfolio): %s", opp.summary())

        if opportunities:
            try:
                self._notifier.notify(opportunities)
            except Exception:
                logger.exception("Notification failed")
                try:
                    self._notifier.notify_error(
                        f"Surge: falha ao notificar {len(opportunities)} opps"
                    )
                except Exception:
                    logger.exception("notify_error failed")
        else:
            logger.info("ScanPortfolio complete — no opportunities")

        return opportunities
