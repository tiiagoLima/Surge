"""Unit tests for ScanPortfolioUseCase."""

from datetime import UTC, datetime

from src.investments.application.scan_portfolio_use_case import ScanPortfolioUseCase
from src.investments.domain.models import Holding, Opportunity, Quote
from src.investments.domain.ports import NotificationPort, PortfolioPort, QuotePort, StoragePort


class FakePortfolio(PortfolioPort):
    def __init__(self, holdings: list[Holding]) -> None:
        self._holdings = holdings

    def save_holding(self, holding: Holding) -> None:
        self._holdings.append(holding)

    def remove_holding(self, ticker: str) -> bool:
        return False

    def get_holding(self, ticker: str) -> Holding | None:
        for h in self._holdings:
            if h.ticker == ticker.upper():
                return h
        return None

    def list_holdings(self) -> list[Holding]:
        return list(self._holdings)


class FakeQuote(QuotePort):
    def __init__(self, quotes: dict[str, Quote]) -> None:
        self._quotes = {k.upper(): v for k, v in quotes.items()}

    def get_quote(self, ticker: str) -> Quote | None:
        return self._quotes.get(ticker.upper())


class FakeNotifier(NotificationPort):
    def __init__(self) -> None:
        self.sent: list[list[Opportunity]] = []

    def notify(self, opps: list[Opportunity]) -> None:
        self.sent.append(list(opps))

    def notify_error(self, message: str) -> None:
        pass


class FakeStorage(StoragePort):
    def __init__(self) -> None:
        self.quotes: list[Quote] = []
        self.opps: list[Opportunity] = []

    def save_quote(self, quote: Quote) -> None:
        self.quotes.append(quote)

    def get_last_quote(self, ticker: str) -> Quote | None:
        return None

    def save_opportunity(self, opp: Opportunity) -> None:
        self.opps.append(opp)


def _quote(ticker: str, price: float, prev: float) -> Quote:
    return Quote(
        ticker=ticker,
        price=price,
        currency="BRL",
        timestamp=datetime.now(UTC),
        source="fake",
        previous_close=prev,
    )


def _holding(ticker: str) -> Holding:
    return Holding(ticker=ticker, quantity=10, currency="BRL", added_at=datetime.now(UTC))


def test_scan_portfolio_detects_drop():
    portfolio = FakePortfolio([_holding("PETR4.SA"), _holding("VALE3.SA")])
    quotes = FakeQuote(
        {
            "PETR4.SA": _quote("PETR4.SA", 90, 100),  # -10% -> opp
            "VALE3.SA": _quote("VALE3.SA", 99, 100),  # -1% -> no
        }
    )
    notifier = FakeNotifier()
    storage = FakeStorage()
    uc = ScanPortfolioUseCase(portfolio, quotes, notifier, storage, drop_threshold_pct=5.0)
    opps = uc.execute()
    assert len(opps) == 1
    assert opps[0].ticker == "PETR4.SA"
    assert len(notifier.sent) == 1
    assert len(storage.opps) == 1


def test_scan_portfolio_empty_holdings():
    portfolio = FakePortfolio([])
    quotes = FakeQuote({})
    notifier = FakeNotifier()
    storage = FakeStorage()
    uc = ScanPortfolioUseCase(portfolio, quotes, notifier, storage)
    assert uc.execute() == []
    assert notifier.sent == []
