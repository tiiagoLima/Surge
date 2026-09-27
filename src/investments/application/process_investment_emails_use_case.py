"""Process investment commands received by email."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.investments.domain.email_models import InvestmentEmailParser
from src.investments.domain.ports import InboxPort, PortfolioPort, QuotePort

logger = logging.getLogger(__name__)


class ProcessInvestmentEmailsUseCase:
    """Validates and records investment purchase emails."""

    def __init__(
        self,
        inbox_port: InboxPort,
        portfolio_port: PortfolioPort,
        quote_port: QuotePort,
        subject_prefix: str = "SURGE: INVESTIMENTO",
    ) -> None:
        self._inbox = inbox_port
        self._portfolio = portfolio_port
        self._quotes = quote_port
        self._subject_prefix = subject_prefix
        self._parser = InvestmentEmailParser()

    def execute(self) -> int:
        """Process valid messages and return the number of imported purchases."""
        processed = 0
        for message in self._inbox.fetch_unprocessed(self._subject_prefix):
            try:
                purchase = self._parser.parse(message.body)
                quote = self._quotes.get_quote(purchase.ticker)
                if quote is None:
                    raise ValueError(f"ticker não encontrado: {purchase.ticker}")
                self._save_purchase(
                    purchase.ticker, purchase.quantity, purchase.unit_price, purchase.currency
                )
                self._inbox.mark_processed(message.uid)
                processed += 1
            except (ValueError, TypeError) as exc:
                logger.warning("Investment email %s rejected: %s", message.uid, exc)
        return processed

    def _save_purchase(
        self, ticker: str, quantity: float, unit_price: float, currency: str
    ) -> None:
        current = self._portfolio.get_holding(ticker)
        if current is None:
            from src.investments.domain.models import Holding

            self._portfolio.save_holding(
                Holding(
                    ticker=ticker,
                    quantity=quantity,
                    avg_price=unit_price,
                    currency=currency,
                    added_at=datetime.now(UTC),
                )
            )
            return
        total_quantity = current.quantity + quantity
        current_cost = (current.avg_price or 0) * current.quantity
        average = (current_cost + unit_price * quantity) / total_quantity
        from src.investments.domain.models import Holding

        self._portfolio.save_holding(
            Holding(
                ticker=current.ticker,
                quantity=total_quantity,
                avg_price=average,
                currency=current.currency,
                added_at=current.added_at,
            )
        )
