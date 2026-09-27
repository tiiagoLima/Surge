"""Ports for the investments bounded context."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.investments.domain.email_models import IncomingEmail
from src.investments.domain.models import Holding, Opportunity, Quote


class QuotePort(ABC):
    """Fetches market quotes for tickers."""

    @abstractmethod
    def get_quote(self, ticker: str) -> Quote | None:
        """Return latest Quote for ticker, or None if unavailable."""

    def get_quotes(self, tickers: list[str]) -> list[Quote]:
        """Batch fetch — default sequential implementation. Adapters may override."""
        result: list[Quote] = []
        for t in tickers:
            q = self.get_quote(t)
            if q is not None:
                result.append(q)
        return result

    def list_market_quotes(self) -> list[Quote]:
        """Return market-wide quotes (e.g. Brapi /api/quote/list). Default empty."""
        return []


class NotificationPort(ABC):
    """Sends notifications about opportunities."""

    @abstractmethod
    def notify(self, opportunities: list[Opportunity]) -> None:
        """Notify about detected opportunities. No-op when list empty."""

    @abstractmethod
    def notify_error(self, message: str) -> None:
        """Notify about a system error (optional channel)."""


class StoragePort(ABC):
    """Persists quotes/opportunities and retrieves history."""

    @abstractmethod
    def save_quote(self, quote: Quote) -> None:
        """Persist a quote for later comparison."""

    @abstractmethod
    def get_last_quote(self, ticker: str) -> Quote | None:
        """Return most recent stored quote for ticker, or None."""

    @abstractmethod
    def save_opportunity(self, opportunity: Opportunity) -> None:
        """Persist a detected opportunity."""

    def get_recent_opportunities(self, limit: int = 20) -> list[Opportunity]:
        """Optional: return recent opportunities."""
        return []


class InboxPort(ABC):
    """Reads and acknowledges messages for inbound automations."""

    @abstractmethod
    def fetch_unprocessed(self, subject_prefix: str) -> list[IncomingEmail]:
        """Return messages matching the automation subject prefix."""

    @abstractmethod
    def mark_processed(self, uid: str) -> None:
        """Mark a message as processed."""


class PortfolioPort(ABC):
    """Manages user's holdings. Strict ISP — no quote/opportunity methods."""

    @abstractmethod
    def save_holding(self, holding: Holding) -> None:
        """Upsert a holding by ticker."""

    @abstractmethod
    def remove_holding(self, ticker: str) -> bool:
        """Remove holding by ticker. Returns True if removed."""

    @abstractmethod
    def get_holding(self, ticker: str) -> Holding | None:
        """Return holding for ticker, or None."""

    @abstractmethod
    def list_holdings(self) -> list[Holding]:
        """Return all holdings ordered by ticker."""
