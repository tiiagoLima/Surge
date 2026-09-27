"""Domain models — immutable value objects (DDD tactical)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    """Market quote for a ticker at a point in time.

    Immutable — represents a historical fact. No behaviour mutates it.

    Attributes:
        ticker: Canonical symbol, e.g. "PETR4.SA" or "AAPL".
        price: Last price in the quote currency.
        currency: ISO 4217 currency code, e.g. "BRL", "USD".
        timestamp: When the quote was observed (UTC).
        source: Provider that produced the quote (yfinance, brapi).
        previous_close: Previous closing price, if available.
    """

    ticker: str
    price: float
    currency: str
    timestamp: datetime
    source: str
    previous_close: float | None = None

    def drop_pct(self) -> float | None:
        """Percentage drop vs previous close. Negative means drop, positive means gain.

        Returns None when previous_close is unavailable or zero.
        """
        if self.previous_close is None or self.previous_close == 0:
            return None
        return ((self.price - self.previous_close) / self.previous_close) * 100

    def is_significant_drop(self, threshold_pct: float) -> bool:
        """True when drop is at least threshold_pct (threshold positive, drop negative)."""
        drop = self.drop_pct()
        if drop is None:
            return False
        return drop <= -abs(threshold_pct)


@dataclass(frozen=True)
class Holding:
    """Position in the user's portfolio.

    Immutable value object — represents a fact at creation time.
    Quantity and avg_price are informational for future P&L alerts,
    not used by the radar itself.

    Attributes:
        ticker: Canonical symbol, e.g. "PETR4.SA".
        quantity: Number of shares/units held.
        avg_price: Average purchase price per unit, if known.
        currency: ISO 4217 code.
        added_at: When holding was added (UTC).
    """

    ticker: str
    quantity: float
    avg_price: float | None = None
    currency: str = "BRL"
    added_at: datetime | None = None


@dataclass(frozen=True)
class Opportunity:
    """Detected market or portfolio opportunity.

    Attributes:
        quote: The quote that triggered the opportunity.
        drop_pct: Actual drop percentage (negative).
        threshold_pct: Threshold that was breached.
        detected_at: When detection happened (UTC).
        holding: Owned position related to the opportunity, when applicable.
    """

    quote: Quote
    drop_pct: float
    threshold_pct: float
    detected_at: datetime
    holding: Holding | None = None

    @property
    def ticker(self) -> str:
        """Return the ticker."""
        return self.quote.ticker

    @property
    def invested_amount(self) -> float | None:
        """Return the position cost basis when average price is available."""
        if self.holding is None or self.holding.avg_price is None:
            return None
        return self.holding.quantity * self.holding.avg_price

    @property
    def current_amount(self) -> float | None:
        """Return the current position value."""
        if self.holding is None:
            return None
        return self.holding.quantity * self.quote.price

    @property
    def pnl_amount(self) -> float | None:
        """Return unrealized profit or loss for the position."""
        invested = self.invested_amount
        current = self.current_amount
        if invested is None or current is None:
            return None
        return current - invested

    @property
    def pnl_pct(self) -> float | None:
        """Return unrealized profit or loss percentage."""
        invested = self.invested_amount
        pnl = self.pnl_amount
        if invested in (None, 0) or pnl is None:
            return None
        return pnl / invested * 100

    def summary(self) -> str:
        """Human-readable one-liner for notifications."""
        summary = (
            f"{self.quote.ticker} caiu {abs(self.drop_pct):.2f}% "
            f"(threshold {self.threshold_pct:.1f}%) — "
            f"{self.quote.price:.2f} {self.quote.currency} "
            f"em {self.detected_at.strftime('%Y-%m-%d %H:%M UTC')} "
            f"[{self.quote.source}]"
        )
        if self.holding is not None:
            summary += f" — posição: {self.holding.quantity:g} unidades"
            if self.pnl_amount is not None and self.pnl_pct is not None:
                summary += f", P&L {self.pnl_amount:+.2f} ({self.pnl_pct:+.2f}%)"
        return summary
