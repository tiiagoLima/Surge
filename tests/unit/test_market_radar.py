"""Unit tests for MarketRadarUseCase."""

from datetime import UTC, datetime

from src.investments.application.market_radar_use_case import MarketRadarUseCase
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
        return None

    def list_holdings(self) -> list[Holding]:
        return list(self._holdings)


class FakeMarket(QuotePort):
    def __init__(self, quotes: list[Quote]) -> None:
        self._quotes = quotes

    def get_quote(self, ticker: str) -> Quote | None:
        for q in self._quotes:
            if q.ticker == ticker.upper():
                return q
        return None

    def list_market_quotes(self) -> list[Quote]:
        return list(self._quotes)


class FakeNotifier(NotificationPort):
    def __init__(self) -> None:
        self.sent: list[list[Opportunity]] = []

    def notify(self, opps: list[Opportunity]) -> None:
        self.sent.append(list(opps))

    def notify_error(self, message: str) -> None:
        pass


class FakeStorage(StoragePort):
    def __init__(self) -> None:
        self.opps: list[Opportunity] = []

    def save_quote(self, quote: Quote) -> None:
        pass

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
        source="brapi",
        previous_close=prev,
    )


def _holding(ticker: str) -> Holding:
    return Holding(ticker=ticker, quantity=10, currency="BRL", added_at=datetime.now(UTC))


def test_radar_filters_holdings_and_threshold():
    portfolio = FakePortfolio([_holding("PETR4.SA")])
    market = FakeMarket(
        [
            _quote("PETR4.SA", 90, 100),  # owned -> ignore even though -10%
            _quote("VALE3.SA", 90, 100),  # not owned, -10% -> opp
            _quote("ITUB4.SA", 99, 100),  # -1% -> ignore
        ]
    )
    notifier = FakeNotifier()
    storage = FakeStorage()
    uc = MarketRadarUseCase(portfolio, market, notifier, storage, drop_threshold_pct=5.0)
    opps = uc.execute()
    assert len(opps) == 1
    assert opps[0].ticker == "VALE3.SA"
    assert len(notifier.sent) == 1


def test_radar_ignores_holdings_without_suffix():
    portfolio = FakePortfolio([_holding("PETR4.SA")])
    market = FakeMarket([_quote("PETR4.SA", 80, 100)])
    uc = MarketRadarUseCase(
        portfolio, market, FakeNotifier(), FakeStorage(), drop_threshold_pct=5.0
    )
    assert uc.execute() == []


def test_radar_empty_market():
    portfolio = FakePortfolio([])
    market = FakeMarket([])
    uc = MarketRadarUseCase(portfolio, market, FakeNotifier(), FakeStorage())
    assert uc.execute() == []
