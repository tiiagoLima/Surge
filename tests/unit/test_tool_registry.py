"""Unit tests for ToolRegistry."""

import json
from typing import Any

import pytest

from src.agent.application.tool_registry import ToolRegistry
from src.agent.domain.models import ToolDefinition


def test_register_and_get_definitions() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="tool_1",
        description="First tool",
        parameters={"type": "object", "properties": {}},
    )
    registry.register_tool(defn, lambda _args: '{"result": "ok"}')

    assert registry.has_tool("tool_1") is True
    assert registry.has_tool("tool_2") is False
    defs = registry.get_definitions()
    assert len(defs) == 1
    assert defs[0].name == "tool_1"


def test_register_empty_name_raises() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(name="   ", description="Empty name")
    with pytest.raises(ValueError, match="Nome da ferramenta não pode ser vazio"):
        registry.register_tool(defn, lambda _args: "")


def test_invoke_unknown_tool_returns_error() -> None:
    registry = ToolRegistry()
    result = registry.invoke("unknown_tool", {}, "call_1")
    assert result.is_error is True
    assert result.tool_call_id == "call_1"
    assert "desconhecida" in result.content


def test_invoke_valid_tool_success() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="echo",
        description="Echo string",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    )
    registry.register_tool(defn, lambda args: json.dumps({"echo": args["text"]}))

    result = registry.invoke("echo", {"text": "hello"}, "call_echo")
    assert result.is_error is False
    assert result.content == '{"echo": "hello"}'


def test_validate_missing_required_argument() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="echo",
        description="Echo string",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    )
    registry.register_tool(defn, lambda args: "ok")

    result = registry.invoke("echo", {}, "call_1")
    assert result.is_error is True
    assert "campo obrigatório ausente: 'text'" in result.content.lower()


def test_validate_extra_fields_rejected() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="echo",
        description="Echo string",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    )
    registry.register_tool(defn, lambda args: "ok")

    result = registry.invoke("echo", {"text": "hello", "extra_param": 123}, "call_1")
    assert result.is_error is True
    assert "campos extras não permitidos" in result.content.lower()
    assert "extra_param" in result.content


def test_validate_argument_types() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="calc",
        description="Calc",
        parameters={
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "rate": {"type": "number"},
                "active": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    )
    registry.register_tool(defn, lambda args: "ok")

    # Boolean passed for integer
    res1 = registry.invoke("calc", {"count": True}, "c1")
    assert res1.is_error is True
    assert "esperado integer" in res1.content.lower()

    # String passed for number
    res2 = registry.invoke("calc", {"rate": "not_a_number"}, "c2")
    assert res2.is_error is True
    assert "esperado number" in res2.content.lower()

    # Int passed for boolean
    res3 = registry.invoke("calc", {"active": 1}, "c3")
    assert res3.is_error is True
    assert "esperado boolean" in res3.content.lower()

    # Valid types
    res4 = registry.invoke("calc", {"count": 10, "rate": 5.5, "active": True}, "c4")
    assert res4.is_error is False


def test_invoke_handler_exception_returns_controlled_error() -> None:
    registry = ToolRegistry()
    defn = ToolDefinition(
        name="failing_tool",
        description="Fails",
        parameters={"type": "object", "properties": {}},
    )

    def failing_handler(_args: dict[str, Any]) -> str:
        raise RuntimeError("Database connection timed out")

    registry.register_tool(defn, failing_handler)

    result = registry.invoke("failing_tool", {}, "call_fail")
    assert result.is_error is True
    assert "erro interno" in result.content.lower()
    # Does not leak technical exception message to the model
    assert "Database connection timed out" not in result.content
