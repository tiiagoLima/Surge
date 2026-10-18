"""Unit tests for AgentRuntime using FakeAgentModel."""

import json
from typing import Any

from src.agent.adapters.outbound.fake_agent_model import FakeAgentModel
from src.agent.adapters.outbound.provider_failure_classifier import (
    ProviderError,
    classify_provider_exception,
)
from src.agent.adapters.tools.portfolio_tools import (
    GET_PORTFOLIO_HOLDINGS_TOOL,
    make_get_portfolio_holdings_handler,
)
from src.agent.application.agent_runtime import AgentRuntime
from src.agent.application.tool_registry import ToolRegistry
from src.agent.domain.models import AgentMessage, ToolCall, ToolDefinition
from src.investments.application.manage_portfolio_use_case import ManagePortfolioUseCase
from src.investments.domain.models import Holding


class FakePortfolioUseCase(ManagePortfolioUseCase):
    """Small explicit fake for ManagePortfolioUseCase."""

    def __init__(self, holdings: list[Holding] | None = None) -> None:
        self._holdings = list(holdings or [])

    def list(self) -> list[Holding]:
        return list(self._holdings)


def _build_test_runtime(
    model: FakeAgentModel,
    holdings: list[Holding] | None = None,
) -> AgentRuntime:
    portfolio_uc = FakePortfolioUseCase(holdings=holdings)

    registry = ToolRegistry()
    registry.register_tool(
        definition=GET_PORTFOLIO_HOLDINGS_TOOL,
        handler=make_get_portfolio_holdings_handler(portfolio_uc),
    )
    return AgentRuntime(model=model, tool_registry=registry, default_max_model_turns=3)


def test_agent_runtime_empty_prompt() -> None:
    model = FakeAgentModel()
    runtime = _build_test_runtime(model)

    response = runtime.run("   ")
    assert "Por favor, envie uma mensagem" in response
    assert len(model.calls) == 0


def test_agent_runtime_direct_response_without_tools() -> None:
    # Model responds directly on turn 1
    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content="Olá! Sou o Surge, seu assistente pessoal.",
            )
        ]
    )
    runtime = _build_test_runtime(model)

    response = runtime.run("Olá, quem é você?")
    assert response == "Olá! Sou o Surge, seu assistente pessoal."
    assert len(model.calls) == 1
    messages_sent = model.calls[0][0]
    assert messages_sent[0].role == "system"
    assert messages_sent[1].role == "user"
    assert messages_sent[1].content == "Olá, quem é você?"


def test_agent_runtime_refuses_coding_request_without_calling_tools() -> None:
    refusal_text = (
        "Não posso escrever, revisar ou executar código, nem acessar arquivos ou comandos. "
        "Sou o Surge, um assistente focado em investimentos e finanças pessoais."
    )
    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content=refusal_text,
            )
        ]
    )
    runtime = _build_test_runtime(model)

    prompt = "Escreva um script em Python para ler e listar todos os arquivos do meu computador."
    response = runtime.run(prompt)

    assert response == refusal_text
    assert len(model.calls) == 1
    messages_sent, tools_provided = model.calls[0]

    # Verify system prompt instructs refusal of coding and terminal/file access tasks
    system_prompt = messages_sent[0].content or ""
    assert "NÃO é um assistente de programação" in system_prompt
    assert (
        "Recuse educadamente qualquer pedido para escrever, revisar, debugar ou executar código"
        in system_prompt
    )
    assert "comandos de terminal" in system_prompt

    # Verify only the allowed portfolio tool was provided (no code/exec/file tools exist)
    assert tools_provided is not None
    assert len(tools_provided) == 1
    assert tools_provided[0].name == "get_portfolio_holdings"

    # User message was passed through correctly
    assert messages_sent[1].role == "user"
    assert messages_sent[1].content == prompt


def test_agent_runtime_valid_tool_call_flow() -> None:
    # User asks: "Quais ativos eu tenho na minha carteira?"
    # Turn 1: Model requests get_portfolio_holdings tool
    # Turn 2: Model returns synthesized answer using tool data
    holdings = [
        Holding(ticker="PETR4.SA", quantity=100.0, avg_price=30.0, currency="BRL"),
        Holding(ticker="VALE3.SA", quantity=50.0, avg_price=60.0, currency="BRL"),
    ]

    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="call_1", name="get_portfolio_holdings", arguments={})],
            ),
            AgentMessage(
                role="assistant",
                content="Você possui 100 cotas de PETR4.SA e 50 cotas de VALE3.SA.",
            ),
        ]
    )
    runtime = _build_test_runtime(model, holdings=holdings)

    response = runtime.run("Quais ativos eu tenho na minha carteira?")
    assert response == "Você possui 100 cotas de PETR4.SA e 50 cotas de VALE3.SA."
    assert len(model.calls) == 2

    # Verify messages in Turn 2
    turn_2_messages = model.calls[1][0]
    assert len(turn_2_messages) == 4
    assert turn_2_messages[0].role == "system"
    assert turn_2_messages[1].role == "user"
    assert turn_2_messages[2].role == "assistant"
    assert turn_2_messages[3].role == "tool"
    assert "PETR4.SA" in (turn_2_messages[3].content or "")
    assert "VALE3.SA" in (turn_2_messages[3].content or "")
    assert '"total_cost": 3000.0' in (turn_2_messages[3].content or "")
    assert '"total_invested": 6000.0' in (turn_2_messages[3].content or "")


def test_agent_runtime_empty_portfolio_flow() -> None:
    # Turn 1: tool call
    # Turn 2: model reports empty portfolio
    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="call_p", name="get_portfolio_holdings", arguments={})],
            ),
            AgentMessage(
                role="assistant",
                content="Sua carteira está vazia, você não possui ativos cadastrados.",
            ),
        ]
    )
    runtime = _build_test_runtime(model, holdings=[])

    response = runtime.run("O que eu tenho investido?")
    assert "carteira está vazia" in response
    assert len(model.calls) == 2
    tool_msg = model.calls[1][0][3]
    assert tool_msg.role == "tool"
    tool_payload = json.loads(tool_msg.content or "{}")
    assert tool_payload["holdings"] == []
    assert tool_payload["total_invested"] == 0.0


def test_agent_runtime_model_requests_unknown_tool() -> None:
    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="call_bad", name="execute_shell", arguments={"cmd": "ls"})],
            ),
            AgentMessage(
                role="assistant",
                content="Não posso executar essa ação pois essa ferramenta não existe.",
            ),
        ]
    )
    runtime = _build_test_runtime(model)

    response = runtime.run("Rode o comando ls")
    assert "Não posso executar essa ação" in response
    assert len(model.calls) == 2

    tool_msg = model.calls[1][0][3]
    assert tool_msg.role == "tool"
    err_content = (tool_msg.content or "").lower()
    assert "não autorizada" in err_content or "desconhecida" in err_content


def test_agent_runtime_model_sends_invalid_arguments() -> None:
    # Model passes extra arguments to get_portfolio_holdings
    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_args",
                        name="get_portfolio_holdings",
                        arguments={"unexpected_param": "foo"},
                    )
                ],
            ),
            AgentMessage(
                role="assistant",
                content="Desculpe, houve um erro nos argumentos da ferramenta.",
            ),
        ]
    )
    runtime = _build_test_runtime(model)

    response = runtime.run("Listar carteira com filtro")
    assert "erro nos argumentos" in response
    tool_msg = model.calls[1][0][3]
    assert tool_msg.role == "tool"
    assert "campos extras não permitidos" in (tool_msg.content or "").lower()


def test_agent_runtime_tool_internal_error_handled_safely() -> None:
    registry = ToolRegistry()
    failing_tool = ToolDefinition(
        name="get_portfolio_holdings",
        description="Fails",
        parameters={"type": "object", "properties": {}},
    )

    def failing_handler(_args: dict[str, Any]) -> str:
        raise RuntimeError("Database connection broke")

    registry.register_tool(failing_tool, failing_handler)

    model = FakeAgentModel(
        responses=[
            AgentMessage(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="call_err", name="get_portfolio_holdings", arguments={})],
            ),
            AgentMessage(
                role="assistant",
                content="Não foi possível consultar a carteira devido a uma falha.",
            ),
        ]
    )
    runtime = AgentRuntime(model=model, tool_registry=registry)

    response = runtime.run("Quais ativos eu tenho?")
    assert "Não foi possível consultar a carteira" in response
    tool_msg = model.calls[1][0][3]
    assert "erro interno" in (tool_msg.content or "").lower()
    # Ensure sensitive internal traceback is NOT passed to the model
    assert "Database connection broke" not in (tool_msg.content or "")


def test_agent_runtime_iteration_limit_reached() -> None:
    # Model keeps asking for tools on every turn
    looping_responses = [
        AgentMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id=f"c_{i}", name="get_portfolio_holdings", arguments={})],
        )
        for i in range(10)
    ]
    model = FakeAgentModel(responses=looping_responses)
    runtime = _build_test_runtime(model)

    response = runtime.run("Loop infinito", max_model_turns=3)
    assert "limite de iterações permitidas" in response
    assert "(3 chamadas ao modelo)" in response
    assert len(model.calls) == 3


def test_agent_runtime_model_api_failure() -> None:
    class FailingModel(FakeAgentModel):
        def generate_reply(self, messages: list[Any], tools: list[Any] | None = None) -> Any:
            raise ConnectionError("Falha de conexão com a API externa")

    runtime = _build_test_runtime(FailingModel())
    response = runtime.run("Olá")
    assert "falha ao comunicar com o modelo de ia" in response.lower()


def test_runtime_provider_failure_is_safe(caplog) -> None:
    class FailingProvider(FakeAgentModel):
        def generate_reply(self, messages, tools=None):
            original = RuntimeError("403 private-financial-payload token=secret-value")
            raise ProviderError(classify_provider_exception(original), original)

    response = _build_test_runtime(FailingProvider()).run("Minha carteira")
    assert "falha ao comunicar com o modelo de IA" in response
    assert "secret-value" not in response + caplog.text
    assert "private-financial-payload" not in response + caplog.text
