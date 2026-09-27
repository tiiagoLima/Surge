"""Unit tests for CompositeQuoteAdapter."""

from datetime import UTC, datetime

from src.investments.adapters.outbound.composite_quote_adapter import CompositeQuoteAdapter
from src.investments.domain.models import Quote
from src.investments.domain.ports import QuotePort


class FakeQuotePort(QuotePort):
    def __init__(
        self,
        quotes: dict[str, Quote | None] | None = None,
        market_quotes: list[Quote] | None = None,
        raise_market_error: bool = False,
    ) -> None:
        self.quotes = quotes or {}
        self.market_quotes = market_quotes or []
        self.raise_market_error = raise_market_error
        self.called_tickers: list[str] = []
        self.list_market_called = False

    def get_quote(self, ticker: str) -> Quote | None:
        self.called_tickers.append(ticker)
        return self.quotes.get(ticker)

    def list_market_quotes(self) -> list[Quote]:
        self.list_market_called = True
        if self.raise_market_error:
            raise RuntimeError("API down")
        return self.market_quotes


def _make_quote(ticker: str, source: str = "fake", price: float = 10.0) -> Quote:
    return Quote(
        ticker=ticker,
        price=price,
        currency="BRL",
        timestamp=datetime.now(UTC),
        source=source,
        previous_close=price,
    )


def test_get_quote_primary_hit():
    q_primary = _make_quote("PETR4.SA", source="primary")
    primary = FakeQuotePort({"PETR4.SA": q_primary})
    fallback = FakeQuotePort({"PETR4.SA": _make_quote("PETR4.SA", source="fallback")})

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    result = adapter.get_quote("PETR4.SA")

    assert result == q_primary
    assert "PETR4.SA" in primary.called_tickers
    assert "PETR4.SA" not in fallback.called_tickers


def test_get_quote_fallback_hit():
    q_fallback = _make_quote("PETR4.SA", source="fallback")
    primary = FakeQuotePort({"PETR4.SA": None})
    fallback = FakeQuotePort({"PETR4.SA": q_fallback})

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    result = adapter.get_quote("PETR4.SA")

    assert result == q_fallback
    assert "PETR4.SA" in primary.called_tickers
    assert "PETR4.SA" in fallback.called_tickers


def test_get_quote_both_none():
    primary = FakeQuotePort()
    fallback = FakeQuotePort()

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    result = adapter.get_quote("UNKNOWN")

    assert result is None
    assert "UNKNOWN" in primary.called_tickers
    assert "UNKNOWN" in fallback.called_tickers


def test_get_quotes_batch():
    q1 = _make_quote("PETR4.SA", source="primary")
    q2 = _make_quote("VALE3.SA", source="fallback")
    primary = FakeQuotePort({"PETR4.SA": q1})
    fallback = FakeQuotePort({"VALE3.SA": q2})

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    results = adapter.get_quotes(["PETR4.SA", "VALE3.SA", "MISSING"])

    assert len(results) == 2
    assert results[0].ticker == "PETR4.SA"
    assert results[0].source == "primary"
    assert results[1].ticker == "VALE3.SA"
    assert results[1].source == "fallback"


def test_list_market_quotes_primary_success():
    q = _make_quote("PETR4.SA", source="primary")
    primary = FakeQuotePort(market_quotes=[q])
    fallback = FakeQuotePort(market_quotes=[_make_quote("VALE3.SA", source="fallback")])

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    results = adapter.list_market_quotes()

    assert results == [q]
    assert primary.list_market_called is True
    assert fallback.list_market_called is False


def test_list_market_quotes_fallback_when_primary_empty():
    q = _make_quote("VALE3.SA", source="fallback")
    primary = FakeQuotePort(market_quotes=[])
    fallback = FakeQuotePort(market_quotes=[q])

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    results = adapter.list_market_quotes()

    assert results == [q]
    assert primary.list_market_called is True
    assert fallback.list_market_called is True


def test_list_market_quotes_fallback_when_primary_raises():
    q = _make_quote("VALE3.SA", source="fallback")
    primary = FakeQuotePort(raise_market_error=True)
    fallback = FakeQuotePort(market_quotes=[q])

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    results = adapter.list_market_quotes()

    assert results == [q]
    assert primary.list_market_called is True
    assert fallback.list_market_called is True


def test_list_market_quotes_both_fail():
    primary = FakeQuotePort(raise_market_error=True)
    fallback = FakeQuotePort(raise_market_error=True)

    adapter = CompositeQuoteAdapter(primary=primary, fallback=fallback)
    results = adapter.list_market_quotes()

    assert results == []
