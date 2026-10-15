"""Unit tests for portfolio tools adapter."""

import json
from datetime import UTC, datetime

from src.agent.adapters.tools.portfolio_tools import (
    GET_PORTFOLIO_HOLDINGS_TOOL,
    make_get_portfolio_holdings_handler,
)
from src.investments.application.manage_portfolio_use_case import ManagePortfolioUseCase
from src.investments.domain.models import Holding


class FakePortfolioUseCase(ManagePortfolioUseCase):
    """Fake portfolio use case for unit tests."""

    def __init__(self, holdings: list[Holding] | None = None) -> None:
        self._holdings = list(holdings or [])

    def list(self) -> list[Holding]:
        return list(self._holdings)


def test_tool_definition_properties() -> None:
    assert GET_PORTFOLIO_HOLDINGS_TOOL.name == "get_portfolio_holdings"
    assert "carteira" in GET_PORTFOLIO_HOLDINGS_TOOL.description.lower()
    assert GET_PORTFOLIO_HOLDINGS_TOOL.parameters.get("additionalProperties") is False


def test_handler_returns_holdings_with_exact_fields() -> None:
    use_case = FakePortfolioUseCase(
        [
            Holding(
                ticker="PETR4.SA",
                quantity=100.0,
                avg_price=34.50,
                currency="BRL",
                added_at=datetime.now(UTC),
            ),
            Holding(
                ticker="AAPL",
                quantity=10.0,
                avg_price=None,  # avg_price not provided
                currency="USD",
                added_at=datetime.now(UTC),
            ),
        ]
    )

    handler = make_get_portfolio_holdings_handler(use_case)
    result_json = handler({})
    data = json.loads(result_json)

    assert "holdings" in data
    assert len(data["holdings"]) == 2
    assert data["total_positions"] == 2
    assert data["total_invested"] is None
    assert data["total_invested_by_currency"] == {"BRL": 3450.0}

    petr = data["holdings"][0]
    assert petr["ticker"] == "PETR4.SA"
    assert petr["quantity"] == 100.0
    assert petr["avg_price"] == 34.50
    assert petr["currency"] == "BRL"
    assert petr["total_cost"] == 3450.0

    aapl = data["holdings"][1]
    assert aapl["ticker"] == "AAPL"
    assert aapl["quantity"] == 10.0
    assert aapl["currency"] == "USD"
    # avg_price was None, so it shouldn't have an invented number or cost
    assert "avg_price" not in aapl
    assert "total_cost" not in aapl


def test_handler_multi_asset_deterministic_calculations() -> None:
    use_case = FakePortfolioUseCase(
        [
            Holding(ticker="PETR4.SA", quantity=100.0, avg_price=30.0, currency="BRL"),
            Holding(ticker="VALE3.SA", quantity=50.0, avg_price=60.0, currency="BRL"),
            Holding(ticker="AAPL", quantity=10.0, avg_price=150.0, currency="USD"),
        ]
    )

    handler = make_get_portfolio_holdings_handler(use_case)
    result_json = handler({})
    data = json.loads(result_json)

    assert data["total_positions"] == 3
    # BRL and USD costs must not be added without an explicit currency conversion.
    assert data["total_invested"] is None
    assert data["total_invested_by_currency"] == {
        "BRL": 6000.0,
        "USD": 1500.0,
    }

    holdings_map = {h["ticker"]: h for h in data["holdings"]}
    assert holdings_map["PETR4.SA"]["total_cost"] == 3000.0
    assert holdings_map["VALE3.SA"]["total_cost"] == 3000.0
    assert holdings_map["AAPL"]["total_cost"] == 1500.0


def test_handler_empty_portfolio() -> None:
    use_case = FakePortfolioUseCase([])

    handler = make_get_portfolio_holdings_handler(use_case)
    result_json = handler({})
    data = json.loads(result_json)

    assert data == {
        "holdings": [],
        "total_positions": 0,
        "total_invested": 0.0,
        "total_invested_by_currency": {},
    }
