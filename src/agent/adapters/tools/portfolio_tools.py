"""Portfolio read-only tool adapter for agent runtime."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from src.agent.domain.models import ToolDefinition
from src.investments.application.manage_portfolio_use_case import ManagePortfolioUseCase

GET_PORTFOLIO_HOLDINGS_TOOL = ToolDefinition(
    name="get_portfolio_holdings",
    description=(
        "Consulta os ativos e posições custodiados na carteira do usuário. "
        "Retorna lista de ativos com ticker, quantidade, moeda, preço médio, "
        "custo total por posição e total investido calculado. "
        "total_invested é null quando há moedas diferentes ou preço médio ausente; "
        "total_invested_by_currency soma apenas custos conhecidos por moeda e pode ser parcial. "
        "Não some moedas diferentes nem estime custos ausentes."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
)


def make_get_portfolio_holdings_handler(
    portfolio_use_case: ManagePortfolioUseCase,
) -> Callable[[dict[str, Any]], str]:
    """Create handler to list portfolio holdings with calculated costs and totals."""

    def handler(_args: dict[str, Any]) -> str:
        summary = portfolio_use_case.get_summary()
        items: list[dict[str, Any]] = []
        for pos in summary.holdings:
            item: dict[str, Any] = {
                "ticker": pos.ticker,
                "quantity": pos.quantity,
                "currency": pos.currency,
            }
            if pos.avg_price is not None:
                item["avg_price"] = pos.avg_price
            if pos.total_cost is not None:
                item["total_cost"] = pos.total_cost
            items.append(item)

        payload: dict[str, Any] = {
            "holdings": items,
            "total_positions": summary.total_positions,
            "total_invested": summary.total_invested,
            "total_invested_by_currency": summary.total_invested_by_currency,
        }
        return json.dumps(payload, ensure_ascii=False)

    return handler
