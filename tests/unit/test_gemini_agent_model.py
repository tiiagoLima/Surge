"""Unit tests for GeminiAgentModel adapter."""

from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agent.adapters.outbound.gemini_agent_model import (
    GeminiAgentModel,
    _is_provider_call_id,
    _normalize_gemini_schema,
)
from src.agent.adapters.tools.portfolio_tools import GET_PORTFOLIO_HOLDINGS_TOOL
from src.agent.domain.models import AgentMessage, ToolCall, ToolDefinition


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        (
            {"type": "object", "properties": {}, "additionalProperties": False},
            {"type": "object", "properties": {}},
        ),
        (
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "positions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"ticker": {"type": "string"}},
                            "required": ["ticker"],
                        },
                    }
                },
            },
            {
                "type": "object",
                "properties": {
                    "positions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"ticker": {"type": "string"}},
                            "required": ["ticker"],
                        },
                    }
                },
            },
        ),
        (
            {"anyOf": [{"type": "object", "additionalProperties": True}, {"type": "null"}]},
            {"anyOf": [{"type": "object"}, {"type": "null"}]},
        ),
    ],
    ids=["simple", "nested-array", "schema-list"],
)
def test_normalize_gemini_schema_copies_without_mutation(
    schema: dict[str, Any], expected: dict[str, Any]
) -> None:
    original = deepcopy(schema)

    normalized = _normalize_gemini_schema(schema)

    assert normalized == expected
    assert normalized is not schema
    assert schema == original


def test_is_provider_call_id() -> None:
    assert _is_provider_call_id("call_gemini_123") is True
    assert _is_provider_call_id("some-uuid-456") is True
    assert _is_provider_call_id("local_call_abc123") is False
    assert _is_provider_call_id(None) is False
    assert _is_provider_call_id("") is False


def test_gemini_agent_model_accepts_strict_portfolio_schema() -> None:
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "Carteira consultada."
    mock_client.models.generate_content.return_value.function_calls = None
    model = GeminiAgentModel(api_key="fake-key")
    model._client = mock_client

    reply = model.generate_reply(
        [AgentMessage(role="user", content="Quais ativos?")],
        tools=[GET_PORTFOLIO_HOLDINGS_TOOL],
    )

    assert reply.content == "Carteira consultada."
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    schema = config.tools[0].function_declarations[0].parameters
    assert schema.additional_properties is None
    assert GET_PORTFOLIO_HOLDINGS_TOOL.parameters["additionalProperties"] is False
    assert "additional_properties" not in GET_PORTFOLIO_HOLDINGS_TOOL.parameters


def test_gemini_agent_model_accepts_nested_strict_schema_without_mutation() -> None:
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "positions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"ticker": {"type": "string"}},
                },
            },
            "metadata": {
                "type": "object",
                "additionalProperties": {"type": "object", "additionalProperties": False},
            },
        },
    }
    original_parameters = deepcopy(parameters)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "OK"
    mock_client.models.generate_content.return_value.function_calls = None
    model = GeminiAgentModel(api_key="fake-key")
    model._client = mock_client

    model.generate_reply(
        [AgentMessage(role="user", content="Consultar carteira")],
        tools=[ToolDefinition(name="nested", description="Nested schema", parameters=parameters)],
    )

    config = mock_client.models.generate_content.call_args.kwargs["config"]
    schema = config.tools[0].function_declarations[0].parameters
    assert schema.additional_properties is None
    assert schema.properties["positions"].items.additional_properties is None
    metadata_schema = schema.properties["metadata"].additional_properties
    assert metadata_schema is None
    assert parameters == original_parameters


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
    # Internal tool messages become user-role function responses for Gemini.
    assert len(called_contents) == 3
    assert [content.role for content in called_contents] == ["user", "model", "user"]

    model_part = called_contents[1].parts[0]
    assert getattr(model_part.function_call, "id", None) == provider_call_id

    tool_part = called_contents[2].parts[0]
    assert getattr(tool_part.function_response, "id", None) == provider_call_id
    assert tool_part.function_response.name == "get_portfolio_holdings"
    assert tool_part.function_response.response == {"holdings": [{"ticker": "PETR4.SA"}]}
    assert messages[2].role == "tool"
    assert messages[2].tool_call_id == provider_call_id


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
    assert [content.role for content in called_contents] == ["user", "model", "user"]

    model_part = called_contents[1].parts[0]
    assert getattr(model_part.function_call, "id", None) is None

    tool_part = called_contents[2].parts[0]
    assert getattr(tool_part.function_response, "id", None) is None
    assert tool_part.function_response.name == "get_portfolio_holdings"
    assert tool_part.function_response.response == {"holdings": [{"ticker": "PETR4.SA"}]}
    assert messages[2].role == "tool"
    assert messages[2].tool_call_id == local_call_id


def test_gemini_agent_model_api_error_logged_and_raised() -> None:
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded")

    model = GeminiAgentModel(api_key="fake-key")
    model._client = mock_client

    with pytest.raises(RuntimeError, match="Quota exceeded"):
        model.generate_reply([AgentMessage(role="user", content="Olá")])
