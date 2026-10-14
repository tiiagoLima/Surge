"""Tool registry for registering, validating, and safely invoking tools."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.domain.models import ToolDefinition, ToolResult
from src.agent.domain.ports import ToolHandler

logger = logging.getLogger(__name__)

TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


class ToolRegistry:
    """Registry maintaining allowed tools with strict schema validation."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}

    def register_tool(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """Register a tool with its schema definition and Python handler."""
        if not definition.name or not definition.name.strip():
            raise ValueError("Nome da ferramenta não pode ser vazio.")
        clean_name = definition.name.strip()
        self._tools[clean_name] = (definition, handler)

    def get_definitions(self) -> list[ToolDefinition]:
        """Return specifications of all registered tools."""
        return [defn for defn, _ in self._tools.values()]

    def has_tool(self, name: str) -> bool:
        """Check if tool name is registered in allowlist."""
        return name in self._tools

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
    ) -> ToolResult:
        """Validate arguments against schema and safely invoke registered handler."""
        if tool_name not in self._tools:
            logger.warning(
                "Tentativa de chamada de ferramenta não autorizada ou desconhecida: '%s'",
                tool_name,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                content=f"Ferramenta desconhecida ou não autorizada: '{tool_name}'.",
                is_error=True,
            )

        definition, handler = self._tools[tool_name]

        val_error = self._validate_arguments(definition.parameters, arguments)
        if val_error:
            logger.warning(
                "Validação de argumentos falhou para ferramenta '%s': %s",
                tool_name,
                val_error,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                content=f"Argumentos inválidos para '{tool_name}': {val_error}",
                is_error=True,
            )

        try:
            content = handler(arguments)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                content=content,
                is_error=False,
            )
        except Exception:
            logger.exception("Falha técnica interna ao executar ferramenta '%s'", tool_name)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                content=f"Ocorreu um erro interno ao consultar '{tool_name}'.",
                is_error=True,
            )

    def _validate_arguments(
        self,
        schema: dict[str, Any],
        arguments: Any,
    ) -> str | None:
        """Strictly validate arguments against schema (types, required, extra fields)."""
        if not isinstance(arguments, dict):
            return "Os argumentos devem ser um objeto/dicionário JSON."

        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", False)

        for req_field in required:
            if req_field not in arguments:
                return f"Campo obrigatório ausente: '{req_field}'."

        if additional_properties is False:
            extra_keys = set(arguments.keys()) - set(properties.keys())
            if extra_keys:
                sorted_extras = sorted(extra_keys)
                return f"Campos extras não permitidos: {sorted_extras}."

        for key, value in arguments.items():
            if key not in properties:
                continue
            prop_schema = properties[key]
            expected_type = prop_schema.get("type")
            if not expected_type or expected_type not in TYPE_MAP:
                continue

            if expected_type in ("integer", "number") and isinstance(value, bool):
                return f"Tipo inválido para '{key}'. Esperado {expected_type}, recebido boolean."

            valid_types = TYPE_MAP[expected_type]
            if not isinstance(value, valid_types):
                actual_type = type(value).__name__
                return (
                    f"Tipo inválido para '{key}'. Esperado {expected_type}, recebido {actual_type}."
                )

        return None
