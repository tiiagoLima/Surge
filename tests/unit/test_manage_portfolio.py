"""Unit tests for ManagePortfolioUseCase."""

from datetime import UTC, datetime

from src.investments.application.manage_portfolio_use_case import ManagePortfolioUseCase
from src.investments.domain.models import Holding, Quote
from src.investments.domain.ports import PortfolioPort, QuotePort


class FakePortfolio(PortfolioPort):
    def __init__(self) -> None:
        self._store: dict[str, Holding] = {}

    def save_holding(self, holding: Holding) -> None:
        self._store[holding.ticker.upper()] = holding

    def remove_holding(self, ticker: str) -> bool:
        return self._store.pop(ticker.upper(), None) is not None

    def get_holding(self, ticker: str) -> Holding | None:
        return self._store.get(ticker.upper())

    def list_holdings(self) -> list[Holding]:
        return sorted(self._store.values(), key=lambda h: h.ticker)


class FakeQuote(QuotePort):
    def __init__(self, valid: set[str]) -> None:
        self.valid = {t.upper() for t in valid}

    def get_quote(self, ticker: str) -> Quote | None:
        if ticker.upper() in self.valid:
            return Quote(
                ticker=ticker.upper(),
                price=10.0,
                currency="BRL",
                timestamp=datetime.now(UTC),
                source="fake",
                previous_close=10.0,
            )
        return None


def test_add_validates_and_persists():
    port = FakePortfolio()
    quotes = FakeQuote({"PETR4.SA"})
    uc = ManagePortfolioUseCase(port, quotes)
    h = uc.add("petr4.sa", quantity=100, avg_price=28.5)
    assert h.ticker == "PETR4.SA"
    assert port.get_holding("PETR4.SA") is not None
    assert len(port.list_holdings()) == 1


def test_add_rejects_unknown_ticker():
    port = FakePortfolio()
    quotes = FakeQuote(set())
    uc = ManagePortfolioUseCase(port, quotes)
    try:
        uc.add("UNKNOWN", quantity=10)
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "não encontrado" in str(e)
    assert port.list_holdings() == []


def test_add_rejects_invalid_quantity():
    port = FakePortfolio()
    quotes = FakeQuote({"PETR4.SA"})
    uc = ManagePortfolioUseCase(port, quotes)
    try:
        uc.add("PETR4.SA", quantity=0)
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_remove_and_list():
    port = FakePortfolio()
    quotes = FakeQuote({"PETR4.SA", "VALE3.SA"})
    uc = ManagePortfolioUseCase(port, quotes)
    uc.add("PETR4.SA", 100)
    uc.add("VALE3.SA", 50)
    assert len(uc.list()) == 2
    assert uc.remove("PETR4.SA") is True
    assert len(uc.list()) == 1
    assert uc.remove("UNKNOWN") is False
