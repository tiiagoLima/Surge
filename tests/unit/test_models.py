"""Unit tests for domain models."""

from datetime import UTC, datetime

from src.investments.domain.models import (
    Holding,
    Opportunity,
    PortfolioSummary,
    PositionSummary,
    Quote,
)


def _quote(price: float = 95.0, prev: float = 100.0) -> Quote:
    return Quote(
        ticker="PETR4.SA",
        price=price,
        currency="BRL",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        source="test",
        previous_close=prev,
    )


def test_drop_pct():
    q = _quote(95, 100)
    assert q.drop_pct() == -5.0


def test_drop_pct_none_when_no_prev():
    q = _quote(95, 100)
    q2 = Quote(
        ticker="AAPL",
        price=150,
        currency="USD",
        timestamp=q.timestamp,
        source="t",
        previous_close=None,
    )
    assert q2.drop_pct() is None


def test_is_significant_drop():
    assert _quote(94, 100).is_significant_drop(5.0) is True
    assert _quote(96, 100).is_significant_drop(5.0) is False
    assert _quote(100, 100).is_significant_drop(5.0) is False


def test_opportunity_summary():
    q = _quote(90, 100)
    opp = Opportunity(quote=q, drop_pct=-10.0, threshold_pct=5.0, detected_at=q.timestamp)
    assert "PETR4.SA" in opp.summary()
    assert "10.00%" in opp.summary()


def test_opportunity_calculates_portfolio_pnl():
    q = _quote(90, 100)
    holding = Holding(ticker="PETR4.SA", quantity=10, avg_price=80, currency="BRL")
    opp = Opportunity(
        quote=q,
        drop_pct=-10.0,
        threshold_pct=5.0,
        detected_at=q.timestamp,
        holding=holding,
    )
    assert opp.invested_amount == 800
    assert opp.current_amount == 900
    assert opp.pnl_amount == 100
    assert opp.pnl_pct == 12.5
    assert "P&L +100.00 (+12.50%)" in opp.summary()


def test_holding_total_cost_calculation():
    h_with_avg = Holding(ticker="PETR4.SA", quantity=100.0, avg_price=34.50, currency="BRL")
    assert h_with_avg.total_cost == 3450.0

    h_without_avg = Holding(ticker="VALE3.SA", quantity=50.0, avg_price=None, currency="BRL")
    assert h_without_avg.total_cost is None


def test_portfolio_summary_models():
    pos = PositionSummary(
        ticker="PETR4.SA",
        quantity=100.0,
        currency="BRL",
        avg_price=34.50,
        total_cost=3450.0,
    )
    assert pos.ticker == "PETR4.SA"
    assert pos.total_cost == 3450.0

    summary = PortfolioSummary(
        holdings=[pos],
        total_positions=1,
        total_invested=3450.0,
        total_invested_by_currency={"BRL": 3450.0},
    )
    assert summary.total_positions == 1
    assert summary.total_invested == 3450.0
    assert summary.total_invested_by_currency["BRL"] == 3450.0
