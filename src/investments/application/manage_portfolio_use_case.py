"""ManagePortfolioUseCase — agnostic to CLI/Telegram (ChatOps ready)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.investments.domain.models import Holding
from src.investments.domain.ports import PortfolioPort, QuotePort

logger = logging.getLogger(__name__)


class ManagePortfolioUseCase:
    """Manages holdings. All methods are input-agnostic.

    Args:
        portfolio_port: Persistence for holdings.
        quote_port: Validates ticker existence (e.g. Brapi) before persist.
    """

    def __init__(self, portfolio_port: PortfolioPort, quote_port: QuotePort) -> None:
        self._portfolio = portfolio_port
        self._quotes = quote_port

    def add(
        self,
        ticker: str,
        quantity: float,
        avg_price: float | None = None,
        currency: str = "BRL",
    ) -> Holding:
        """Add or update a holding after validating ticker via QuotePort.

        Raises:
            ValueError: if ticker invalid, quantity <=0, or quote not found.
        """
        norm = ticker.strip().upper()
        if not norm:
            raise ValueError("ticker vazio")
        if quantity <= 0:
            raise ValueError("quantity deve ser > 0")
        if avg_price is not None and avg_price <= 0:
            raise ValueError("avg_price deve ser > 0 se informado")

        # Validate via external quote (Brapi free). Must exist.
        quote = self._quotes.get_quote(norm)
        if quote is None:
            # Try with .SA suffix for B3 if not already
            alt = norm if "." in norm else f"{norm}.SA"
            if alt != norm:
                quote = self._quotes.get_quote(alt)
            if quote is None:
                raise ValueError(f"ticker não encontrado: {ticker}")

        # Use canonical ticker from quote if available, else normalized
        canonical = quote.ticker if quote else norm
        holding = Holding(
            ticker=canonical,
            quantity=float(quantity),
            avg_price=float(avg_price) if avg_price is not None else None,
            currency=currency.upper(),
            added_at=datetime.now(UTC),
        )
        self._portfolio.save_holding(holding)
        logger.info(
            "Holding added: %s qty=%.2f avg=%s", holding.ticker, holding.quantity, holding.avg_price
        )
        return holding

    def remove(self, ticker: str) -> bool:
        """Remove holding. Returns True if removed."""
        norm = ticker.strip().upper()
        if not norm:
            raise ValueError("ticker vazio")
        removed = self._portfolio.remove_holding(norm)
        if not removed:
            # Try alternate normalization
            alt = norm if "." in norm else f"{norm}.SA"
            if alt != norm:
                removed = self._portfolio.remove_holding(alt)
        logger.info("Holding remove %s -> %s", ticker, removed)
        return removed

    def list(self) -> list[Holding]:
        """Return all holdings ordered by ticker."""
        return self._portfolio.list_holdings()

    def get(self, ticker: str) -> Holding | None:
        """Return single holding or None."""
        holding = self._portfolio.get_holding(ticker.strip().upper())
        if holding is None:
            alt = ticker.strip().upper()
            if "." not in alt:
                holding = self._portfolio.get_holding(f"{alt}.SA")
        return holding
