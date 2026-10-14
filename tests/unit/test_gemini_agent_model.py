"""Unit tests for GeminiAgentModel adapter."""

from unittest.mock import MagicMock

import pytest

from src.agent.adapters.outbound.gemini_agent_model import (
    GeminiAgentModel,
    _is_provider_call_id,
)
from src.agent.domain.models import AgentMessage, ToolCall, ToolDefinition


def test_is_provider_call_id() -> None:
    assert _is_provider_call_id("call_gemini_123") is True
    assert _is_provider_call_id("some-uuid-456") is True
    assert _is_provider_call_id("local_call_abc123") is False
    assert _is_provider_call_id(None) is False
    assert _is_provider_call_id("") is False


def test_gemini_agent_model_empty_api_key_raises() -> None:
    model = GeminiAgentModel(api_key="  ")
    with pytest.raises(ValueError, match="SURGE_GEMINI_API_KEY não configurada"):
        model.generate_reply([AgentMessage(role="user", content="Olá")])


def test_gemini_agent_model_successful_text_generation() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.function_calls = None
    mock_response.text = "Olá! Como posso ajudar?"
    mock_client.models.generate_content.return_value = mock_response

    model = GeminiAgentModel(api_key="fake-key", model="gemini-2.5-flash")
    model._client = mock_client

    messages = [
        AgentMessage(role="system", content="Instrução do sistema."),
        AgentMessage(role="user", content="Oi"),
    ]
    reply = model.generate_reply(messages)

    assert reply.role == "assistant"
    assert reply.content == "Olá! Como posso ajudar?"
    assert reply.tool_calls is None
    assert mock_client.models.generate_content.called


def test_gemini_agent_model_function_call_mapping_with_provider_id() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()

    mock_fc = MagicMock()
    mock_fc.id = "gemini_call_xyz"
    mock_fc.name = "get_portfolio_holdings"
    mock_fc.args = {}

    mock_response.function_calls = [mock_fc]
    mock_response.text = None
    mock_client.models.generate_content.return_value = mock_response

    model = GeminiAgentModel(api_key="fake-key", model="gemini-2.5-flash")
    model._client = mock_client

    tool_def = ToolDefinition(
        name="get_portfolio_holdings",
        description="Consulta ativos",
        parameters={"type": "object", "properties": {}},
    )

    messages = [AgentMessage(role="user", content="Quais meus ativos?")]
    reply = model.generate_reply(messages, tools=[tool_def])

    assert reply.role == "assistant"
    assert reply.tool_calls is not None
    assert len(reply.tool_calls) == 1
    tc = reply.tool_calls[0]
    assert tc.name == "get_portfolio_holdings"
    assert tc.id == "gemini_call_xyz"


def test_gemini_agent_model_function_call_mapping_without_provider_id() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()

    mock_fc = MagicMock()
    mock_fc.id = None
    mock_fc.name = "get_portfolio_holdings"
    mock_fc.args = {}

    mock_response.function_calls = [mock_fc]
    mock_response.text = None
    mock_client.models.generate_content.return_value = mock_response

    model = GeminiAgentModel(api_key="fake-key", model="gemini-2.5-flash")
    model._client = mock_client

    messages = [AgentMessage(role="user", content="Quais meus ativos?")]
    reply = model.generate_reply(messages)

    assert reply.tool_calls is not None
    assert len(reply.tool_calls) == 1
    tc = reply.tool_calls[0]
    assert tc.id.startswith("local_call_")


def test_gemini_agent_model_preserves_provider_call_id_in_outbound_messages() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.function_calls = None
    mock_response.text = "Você tem 100 cotas."
    mock_client.models.generate_content.return_value = mock_response

    model = GeminiAgentModel(api_key="fake-key", model="gemini-2.5-flash")
    model._client = mock_client

    provider_call_id = "provider_call_abc123"
    messages = [
        AgentMessage(role="user", content="Quais ativos?"),
        AgentMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id=provider_call_id, name="get_portfolio_holdings", arguments={})],
        ),
        AgentMessage(
            role="tool",
            name="get_portfolio_holdings",
            content='{"holdings": [{"ticker": "PETR4.SA"}]}',
            tool_call_id=provider_call_id,
        ),
    ]

    model.generate_reply(messages)

    called_contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    # called_contents: [0]=user, [1]=model (assistant), [2]=tool
    assert len(called_contents) == 3

    model_part = called_contents[1].parts[0]
    assert getattr(model_part.function_call, "id", None) == provider_call_id

    tool_part = called_contents[2].parts[0]
    assert getattr(tool_part.function_response, "id", None) == provider_call_id


def test_gemini_agent_model_omits_local_call_id_from_outbound_messages() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.function_calls = None
    mock_response.text = "Você tem 100 cotas."
    mock_client.models.generate_content.return_value = mock_response

    model = GeminiAgentModel(api_key="fake-key", model="gemini-2.5-flash")
    model._client = mock_client

    local_call_id = "local_call_deadbeef"
    messages = [
        AgentMessage(role="user", content="Quais ativos?"),
        AgentMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id=local_call_id, name="get_portfolio_holdings", arguments={})],
        ),
        AgentMessage(
            role="tool",
            name="get_portfolio_holdings",
            content='{"holdings": [{"ticker": "PETR4.SA"}]}',
            tool_call_id=local_call_id,
        ),
    ]

    model.generate_reply(messages)

    called_contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert len(called_contents) == 3

    model_part = called_contents[1].parts[0]
    assert getattr(model_part.function_call, "id", None) is None

    tool_part = called_contents[2].parts[0]
    assert getattr(tool_part.function_response, "id", None) is None


def test_gemini_agent_model_api_error_logged_and_raised() -> None:
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded")

    model = GeminiAgentModel(api_key="fake-key")
    model._client = mock_client

    with pytest.raises(RuntimeError, match="Quota exceeded"):
        model.generate_reply([AgentMessage(role="user", content="Olá")])
