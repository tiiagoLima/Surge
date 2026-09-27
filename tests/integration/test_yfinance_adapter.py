"""Integration tests — require network. Run with pytest tests/integration."""

import pytest

from src.investments.adapters.outbound.yfinance_adapter import YFinanceAdapter

pytestmark = pytest.mark.integration


def test_yfinance_fetch_aapl():
    adapter = YFinanceAdapter()
    quote = adapter.get_quote("AAPL")
    # Network may be unavailable in CI — allow None but check shape when present
    if quote is None:
        pytest.skip("yfinance unavailable or rate-limited")
    assert quote.ticker == "AAPL"
    assert quote.price > 0
    assert quote.currency
    assert quote.source == "yfinance"
