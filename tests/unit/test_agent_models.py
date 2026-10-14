"""Unit tests for agent domain models."""

from src.agent.domain.models import AgentMessage, ToolCall, ToolDefinition, ToolResult


def test_tool_definition_creation() -> None:
    defn = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    assert defn.name == "test_tool"
    assert defn.description == "A test tool"
    assert defn.parameters["type"] == "object"


def test_tool_call_and_result_creation() -> None:
    call = ToolCall(id="call_1", name="get_data", arguments={"page": 1})
    assert call.id == "call_1"
    assert call.name == "get_data"
    assert call.arguments == {"page": 1}

    result = ToolResult(
        tool_call_id="call_1",
        name="get_data",
        content='{"items": []}',
        is_error=False,
    )
    assert result.tool_call_id == "call_1"
    assert result.content == '{"items": []}'
    assert not result.is_error


def test_agent_message_creation() -> None:
    msg_user = AgentMessage(role="user", content="Olá!")
    assert msg_user.role == "user"
    assert msg_user.content == "Olá!"
    assert msg_user.tool_calls is None

    msg_assistant = AgentMessage(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="c1", name="tool_a", arguments={})],
    )
    assert msg_assistant.role == "assistant"
    assert len(msg_assistant.tool_calls or []) == 1

    msg_tool = AgentMessage(
        role="tool",
        content='{"status": "ok"}',
        tool_call_id="c1",
        name="tool_a",
    )
    assert msg_tool.role == "tool"
    assert msg_tool.tool_call_id == "c1"
    assert msg_tool.name == "tool_a"
