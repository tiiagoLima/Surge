"""Unit tests for the Telegram finance bot inbound adapter."""

from typing import Any

from src.finances.adapters.inbound.telegram_bot_adapter import TelegramFinanceBotAdapter
from src.finances.application.manage_budget_use_case import (
    GetMonthlySummaryUseCase,
    SetBudgetUseCase,
)
from src.finances.application.register_expense_use_case import RegisterExpenseUseCase
from src.finances.domain.models import CategoryBudget, ExpenseCategory, Transaction
from src.finances.domain.ports import BudgetPort, TransactionPort
from src.investments.application.manage_portfolio_use_case import ManagePortfolioUseCase
from src.investments.domain.models import Holding, Quote
from src.investments.domain.ports import PortfolioPort, QuotePort


class FakeHttpResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._json_data

    def raise_for_status(self) -> None:
        pass


class FakeHttpSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, json: dict[str, Any], timeout: int = 10) -> FakeHttpResponse:
        self.calls.append((url, json))
        return FakeHttpResponse({"ok": True, "result": []})


class DummyTransactionPort(TransactionPort):
    def __init__(self) -> None:
        self.saved: list[Transaction] = []

    def save(self, transaction: Transaction) -> None:
        self.saved.append(transaction)

    def get_spent_by_category(self, category: ExpenseCategory, month: str) -> float:
        return 100.0

    def list_by_month(self, month: str) -> list[Transaction]:
        return self.saved


class DummyBudgetPort(BudgetPort):
    def __init__(self) -> None:
        self.budgets: dict[tuple[ExpenseCategory, str], CategoryBudget] = {}

    def save_budget(self, budget: CategoryBudget) -> None:
        self.budgets[(budget.category, budget.month)] = budget

    def get_budget_by_category(
        self, category: ExpenseCategory, month: str
    ) -> CategoryBudget | None:
        return self.budgets.get((category, month))


class DummyPortfolioPort(PortfolioPort):
    def __init__(self, holdings: list[Holding] | None = None) -> None:
        self.holdings = {h.ticker: h for h in (holdings or [])}

    def save_holding(self, holding: Holding) -> None:
        self.holdings[holding.ticker] = holding

    def remove_holding(self, ticker: str) -> bool:
        return self.holdings.pop(ticker, None) is not None

    def get_holding(self, ticker: str) -> Holding | None:
        return self.holdings.get(ticker)

    def list_holdings(self) -> list[Holding]:
        return list(self.holdings.values())


class DummyQuotePort(QuotePort):
    def __init__(self, valid_tickers: list[str] | None = None) -> None:
        self.valid = valid_tickers or ["PETR4.SA", "VALE3.SA"]

    def get_quote(self, ticker: str) -> Quote | None:
        canonical = ticker if "." in ticker else f"{ticker}.SA"
        if canonical in self.valid or ticker in self.valid:
            from datetime import UTC, datetime

            return Quote(
                ticker=canonical,
                price=30.0,
                currency="BRL",
                timestamp=datetime.now(UTC),
                source="test",
            )
        return None

    def list_market_quotes(self) -> list[Quote]:
        return []


def _make_bot(
    fake_session: FakeHttpSession,
    allowed_chat_id: str = "12345",
    holdings: list[Holding] | None = None,
) -> TelegramFinanceBotAdapter:
    tx_port = DummyTransactionPort()
    bg_port = DummyBudgetPort()
    port_port = DummyPortfolioPort(holdings=holdings)
    quote_port = DummyQuotePort()
    register_uc = RegisterExpenseUseCase(transaction_port=tx_port, budget_port=bg_port)
    set_budget_uc = SetBudgetUseCase(budget_port=bg_port)
    summary_uc = GetMonthlySummaryUseCase(transaction_port=tx_port, budget_port=bg_port)
    portfolio_uc = ManagePortfolioUseCase(portfolio_port=port_port, quote_port=quote_port)
    return TelegramFinanceBotAdapter(
        bot_token="fake_token",
        allowed_chat_id=allowed_chat_id,
        register_expense_use_case=register_uc,
        set_budget_use_case=set_budget_uc,
        get_summary_use_case=summary_uc,
        portfolio_use_case=portfolio_uc,
        session=fake_session,  # type: ignore[arg-type]
    )


def test_unauthorized_user_message_is_rejected() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    bot.process_update(
        {
            "message": {
                "from": {"id": 99999},
                "chat": {"id": 99999},
                "text": "/start",
            }
        }
    )

    assert len(session.calls) == 1
    url, payload = session.calls[0]
    assert url.endswith("/sendMessage")
    assert payload["chat_id"] == "99999"
    assert "Acesso não autorizado" in payload["text"]


def test_main_menu_sent_on_start() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "/start",
            }
        }
    )

    assert len(session.calls) == 1
    _, payload = session.calls[0]
    assert "Surge Assistant" in payload["text"]
    keyboard = payload["reply_markup"]["inline_keyboard"]
    assert keyboard[0][0]["text"] == "➕ Registrar Gasto"
    assert keyboard[0][1]["text"] == "📊 Resumo Gastos"
    assert keyboard[1][1]["text"] == "💼 Minha Carteira"
    assert keyboard[2][0]["text"] == "➕ Adicionar Ativo"
    assert keyboard[2][1]["text"] == "➖ Remover Ativo"


def test_click_expense_menu_shows_categories() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    bot.process_update(
        {
            "callback_query": {
                "id": "query_1",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "menu:expense",
            }
        }
    )

    # 1 answerCallbackQuery + 1 sendMessage
    assert len(session.calls) == 2
    assert session.calls[0][0].endswith("/answerCallbackQuery")
    assert session.calls[1][0].endswith("/sendMessage")
    keyboard = session.calls[1][1]["reply_markup"]["inline_keyboard"]
    callbacks = [btn["callback_data"] for row in keyboard for btn in row]
    assert "exp_cat:FOOD" in callbacks
    assert "exp_cat:LEISURE" in callbacks


def test_expense_registration_flow() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    # Step 1: select category
    bot.process_update(
        {
            "callback_query": {
                "id": "query_2",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "exp_cat:LEISURE",
            }
        }
    )

    # Step 2: send amount and description
    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "55.00 Cinema",
            }
        }
    )

    last_url, last_payload = session.calls[-1]
    assert last_url.endswith("/sendMessage")
    assert "Gasto registrado com sucesso!" in last_payload["text"]
    assert "55.00" in last_payload["text"]
    assert "Lazer (Cinema)" in last_payload["text"]


def test_budget_setting_flow() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    # Step 1: select budget category
    bot.process_update(
        {
            "callback_query": {
                "id": "query_3",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "bud_cat:FOOD",
            }
        }
    )

    # Step 2: send budget amount
    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "600",
            }
        }
    )

    _, last_payload = session.calls[-1]
    assert "Teto configurado com sucesso!" in last_payload["text"]
    assert "600.00" in last_payload["text"]


def test_cancel_operation_resets_state() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    # Start category selection
    bot.process_update(
        {
            "callback_query": {
                "id": "query_4",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "exp_cat:FOOD",
            }
        }
    )

    # Cancel
    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "/cancelar",
            }
        }
    )

    assert "Operação cancelada" in session.calls[-2][1]["text"]
    assert "Surge Assistant" in session.calls[-1][1]["text"]


def test_portfolio_empty_view() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345", holdings=[])

    bot.process_update(
        {
            "callback_query": {
                "id": "query_p1",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "menu:portfolio",
            }
        }
    )

    last_url, last_payload = session.calls[-1]
    assert last_url.endswith("/sendMessage")
    assert "carteira está vazia" in last_payload["text"]
    assert "➕ Adicionar Ativo" in str(last_payload["reply_markup"])


def test_portfolio_view_with_holdings() -> None:
    session = FakeHttpSession()
    h = Holding(ticker="PETR4.SA", quantity=100.0, avg_price=30.0, currency="BRL")
    bot = _make_bot(session, allowed_chat_id="12345", holdings=[h])

    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "/carteira",
            }
        }
    )

    last_url, last_payload = session.calls[-1]
    assert last_url.endswith("/sendMessage")
    assert "PETR4.SA" in last_payload["text"]
    assert "100 cotas" in last_payload["text"]
    assert "30.00" in last_payload["text"]


def test_portfolio_add_flow_success() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    # Step 1: click add asset button
    bot.process_update(
        {
            "callback_query": {
                "id": "query_add",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "menu:portfolio_add",
            }
        }
    )
    assert "Adicionar Ativo à Carteira" in session.calls[-1][1]["text"]

    # Step 2: send ticker, quantity, and avg price
    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "PETR4 100 30.00",
            }
        }
    )

    last_payload = session.calls[-1][1]
    assert "Ativo adicionado com sucesso!" in last_payload["text"]
    assert "PETR4.SA" in last_payload["text"]
    assert "100" in last_payload["text"]
    assert "30.00" in last_payload["text"]


def test_portfolio_add_direct_command() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "/ativo VALE3 50 60.50",
            }
        }
    )

    last_payload = session.calls[-1][1]
    assert "Ativo adicionado com sucesso!" in last_payload["text"]
    assert "VALE3.SA" in last_payload["text"]
    assert "50" in last_payload["text"]


def test_portfolio_add_invalid_ticker_error() -> None:
    session = FakeHttpSession()
    bot = _make_bot(session, allowed_chat_id="12345")

    bot.process_update(
        {
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "/ativo INEXISTENTE3 100 10",
            }
        }
    )

    last_payload = session.calls[-1][1]
    assert "Erro ao adicionar ativo" in last_payload["text"]
    assert "não encontrado" in last_payload["text"]


def test_portfolio_remove_flow() -> None:
    session = FakeHttpSession()
    h = Holding(ticker="PETR4.SA", quantity=100.0, avg_price=30.0, currency="BRL")
    bot = _make_bot(session, allowed_chat_id="12345", holdings=[h])

    # Step 1: click remove asset
    bot.process_update(
        {
            "callback_query": {
                "id": "query_rm",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "menu:portfolio_rm",
            }
        }
    )

    last_payload = session.calls[-1][1]
    assert "remover" in last_payload["text"].lower()
    assert "port_rm:PETR4.SA" in str(last_payload["reply_markup"])

    # Step 2: click ticker button to remove
    bot.process_update(
        {
            "callback_query": {
                "id": "query_confirm_rm",
                "from": {"id": 12345},
                "message": {"chat": {"id": 12345}},
                "data": "port_rm:PETR4.SA",
            }
        }
    )

    final_payload = session.calls[-1][1]
    assert "removido da carteira com sucesso" in final_payload["text"]
    assert "PETR4.SA" in final_payload["text"]
