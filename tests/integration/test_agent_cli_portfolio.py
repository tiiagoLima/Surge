"""Offline CLI-to-model portfolio flow using a temporary SQLite database."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import main as cli
from src.agent.adapters.outbound.fake_agent_model import FakeAgentModel
from src.agent.domain.models import AgentMessage, ToolCall
from src.investments.adapters.outbound.sqlite_repository import SqliteRepository
from src.investments.domain.models import Holding, Quote
from src.investments.domain.ports import QuotePort
from src.shared.database.migrations import provision_database


class NoQuoteAccess(QuotePort):
    """Fail if the read-only assistant tries to fetch a quote."""

    def get_quote(self, ticker: str) -> Quote | None:
        raise AssertionError("Portfolio reading must not fetch quotes")


@pytest.mark.parametrize(
    ("holdings", "expected_total", "expected_by_currency"),
    [
        pytest.param([], 0.0, {}, id="empty"),
        pytest.param(
            [
                Holding("PETR4.SA", 100, 30, "BRL"),
                Holding("VALE3.SA", 50, 60, "BRL"),
            ],
            6000.0,
            {"BRL": 6000.0},
            id="single-currency",
        ),
        pytest.param(
            [Holding("PETR4.SA", 100, 30, "BRL"), Holding("AAPL", 2, 150, "USD")],
            None,
            {"BRL": 3000.0, "USD": 300.0},
            id="multiple-currencies",
        ),
        pytest.param(
            [Holding("PETR4.SA", 100, 30), Holding("VALE3.SA", 50)],
            None,
            {"BRL": 3000.0},
            id="missing-average-price",
        ),
        pytest.param(
            [Holding("VALE3.SA", 50)],
            None,
            {},
            id="all-average-prices-missing",
        ),
        pytest.param(
            [Holding("PETR4.SA", 100, 30), Holding("AAPL", 2, currency="USD")],
            None,
            {"BRL": 3000.0},
            id="foreign-position-without-average-price",
        ),
    ],
)
def test_ask_reads_sqlite_portfolio_through_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    holdings: list[Holding],
    expected_total: float | None,
    expected_by_currency: dict[str, float],
) -> None:
    db_path = tmp_path / "portfolio.db"
    provision_database(db_path)
    seed_repository = SqliteRepository(db_path)
    for holding in holdings:
        seed_repository.save_holding(holding)

    # Reopen the file so the runtime must read persisted fixture data, not a fake list.
    repository = SqliteRepository(db_path)
    before = repository.list_holdings()
    database_before = db_path.read_bytes()
    settings = SimpleNamespace(
        log_level="INFO", gemini_api_key="offline-test-key", gemini_model="offline-test-model"
    )
    fake_model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                tool_calls=[ToolCall(id="portfolio-call", name="get_portfolio_holdings")],
            ),
            AgentMessage(role="assistant", content="Resposta final do modelo fake."),
        ]
    )

    def build_fake_model(*, api_key: str, model: str) -> FakeAgentModel:
        assert api_key == "offline-test-key"
        assert model == "offline-test-model"
        return fake_model

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        cli,
        "_build_ports",
        lambda: (settings, repository, NoQuoteAccess(), None, repository),
    )
    monkeypatch.setattr(cli, "GeminiAgentModel", build_fake_model)
    prompt = "Quais ativos e custos tenho na carteira?"
    monkeypatch.setattr("sys.argv", ["surge", "ask", prompt])

    cli.main()

    captured = capsys.readouterr()
    assert captured.out == "Surge pensando...\n\nResposta final do modelo fake.\n"
    assert captured.err == ""
    assert len(fake_model.calls) == 2
    first_messages, tools = fake_model.calls[0]
    assert first_messages[-1].role == "user"
    assert first_messages[-1].content == prompt
    assert tools is not None
    assert [tool.name for tool in tools] == ["get_portfolio_holdings"]
    second_messages, _ = fake_model.calls[1]
    assert [message.role for message in second_messages] == ["system", "user", "assistant", "tool"]
    tool_message = second_messages[-1]
    assert tool_message.tool_call_id == "portfolio-call"
    payload = json.loads(tool_message.content or "{}")
    assert payload["total_positions"] == len(holdings)
    assert payload["total_invested"] == expected_total
    assert payload["total_invested_by_currency"] == expected_by_currency
    positions = {position["ticker"]: position for position in payload["holdings"]}
    assert set(positions) == {holding.ticker for holding in holdings}
    for holding in holdings:
        position = positions[holding.ticker]
        assert position["quantity"] == holding.quantity
        assert position["currency"] == holding.currency
        if holding.avg_price is None:
            assert "avg_price" not in position
            assert "total_cost" not in position
        else:
            assert position["avg_price"] == holding.avg_price
            assert position["total_cost"] == holding.total_cost

    assert repository.list_holdings() == before
    assert db_path.read_bytes() == database_before
