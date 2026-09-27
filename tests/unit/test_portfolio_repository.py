"""Unit tests for PortfolioPort via SqliteRepository (in-memory)."""

from datetime import UTC, datetime

from src.investments.adapters.outbound.sqlite_repository import SqliteRepository
from src.investments.domain.models import Holding


def _holding(ticker: str = "PETR4.SA", qty: float = 100, avg: float | None = 28.5) -> Holding:
    return Holding(
        ticker=ticker,
        quantity=qty,
        avg_price=avg,
        currency="BRL",
        added_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_save_and_get_holding():
    repo = SqliteRepository(db_path=":memory:")
    repo.save_holding(_holding("PETR4.SA", 100, 28.5))
    h = repo.get_holding("petr4.sa")  # case-insensitive
    assert h is not None
    assert h.ticker == "PETR4.SA"
    assert h.quantity == 100
    assert h.avg_price == 28.5
    assert h.currency == "BRL"


def test_list_holdings_ordered():
    repo = SqliteRepository(db_path=":memory:")
    repo.save_holding(_holding("VALE3.SA"))
    repo.save_holding(_holding("PETR4.SA"))
    repo.save_holding(_holding("AAPL"))
    tickers = [h.ticker for h in repo.list_holdings()]
    assert tickers == ["AAPL", "PETR4.SA", "VALE3.SA"]


def test_upsert_updates_quantity():
    repo = SqliteRepository(db_path=":memory:")
    repo.save_holding(_holding("PETR4.SA", 100, 28.5))
    repo.save_holding(_holding("PETR4.SA", 150, 30.0))
    h = repo.get_holding("PETR4.SA")
    assert h is not None
    assert h.quantity == 150
    assert h.avg_price == 30.0
    assert len(repo.list_holdings()) == 1


def test_remove_holding():
    repo = SqliteRepository(db_path=":memory:")
    repo.save_holding(_holding("PETR4.SA"))
    assert repo.remove_holding("PETR4.SA") is True
    assert repo.get_holding("PETR4.SA") is None
    assert repo.remove_holding("PETR4.SA") is False
    assert repo.list_holdings() == []


def test_get_missing_returns_none():
    repo = SqliteRepository(db_path=":memory:")
    assert repo.get_holding("UNKNOWN") is None
    assert repo.list_holdings() == []
