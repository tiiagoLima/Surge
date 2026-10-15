"""Outbound adapter for Google Gemini model supporting tool calling."""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import uuid
from typing import Any

from src.agent.domain.models import AgentMessage, ToolCall, ToolDefinition
from src.agent.domain.ports import AgentModelPort

try:
    genai: Any = importlib.import_module("google.genai")
    types: Any = importlib.import_module("google.genai.types")
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)


def _normalize_gemini_schema(schema: Any) -> Any:
    """Copy a schema, omitting additionalProperties at the Gemini API boundary."""
    if isinstance(schema, list):
        return [_normalize_gemini_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    normalized: dict[str, Any] = {}
    for key, value in schema.items():
        # The Gemini API rejects this JSON-Schema keyword in function parameters.
        # Keep it in the internal contract, but omit it at the provider boundary.
        if key == "additionalProperties":
            continue
        normalized[key] = _normalize_gemini_schema(value)
    return normalized


def _is_provider_call_id(call_id: str | None) -> bool:
    """Check if tool call ID was provided by Gemini rather than generated locally."""
    if not call_id:
        return False
    return not call_id.startswith("local_call_")


class GeminiAgentModel(AgentModelPort):
    """Adapter invoking Gemini models using the official google-genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        """Initialize adapter with credentials and model name."""
        self._api_key = str(api_key).strip()
        self._model = model
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise ValueError("SURGE_GEMINI_API_KEY não configurada no ambiente.")
        if genai is None:
            raise RuntimeError("Biblioteca 'google-genai' não está disponível no ambiente.")
        self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate_reply(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AgentMessage:
        """Generate response from Gemini, converting messages and tool definitions."""
        client = self._ensure_client()

        system_instruction: str | None = None
        gemini_contents: list[Any] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
                continue

            if msg.role == "user":
                part = types.Part.from_text(text=msg.content or "")
                gemini_contents.append(types.Content(role="user", parts=[part]))
                continue

            if msg.role == "assistant":
                parts: list[Any] = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        provider_id = tc.id if _is_provider_call_id(tc.id) else None
                        fc_sig = inspect.signature(types.Part.from_function_call)
                        has_fc_id_param = "id" in fc_sig.parameters
                        if has_fc_id_param and provider_id:
                            part = types.Part.from_function_call(
                                name=tc.name,
                                args=tc.arguments,
                                id=provider_id,
                            )
                        else:
                            part = types.Part.from_function_call(
                                name=tc.name,
                                args=tc.arguments,
                            )
                            fc_obj = getattr(part, "function_call", None)
                            if provider_id and fc_obj:
                                fc_obj.id = provider_id
                        parts.append(part)
                gemini_contents.append(types.Content(role="model", parts=parts))
                continue

            if msg.role == "tool":
                # Parse JSON content into dict for Gemini FunctionResponse if possible
                response_data: dict[str, Any]
                try:
                    parsed = json.loads(msg.content or "{}")
                    response_data = parsed if isinstance(parsed, dict) else {"result": parsed}
                except Exception:
                    response_data = {"result": msg.content or ""}

                provider_id = msg.tool_call_id if _is_provider_call_id(msg.tool_call_id) else None
                fr_sig = inspect.signature(types.Part.from_function_response)
                has_fr_id_param = "id" in fr_sig.parameters
                if has_fr_id_param and provider_id:
                    part = types.Part.from_function_response(
                        name=msg.name or "tool",
                        response=response_data,
                        id=provider_id,
                    )
                else:
                    part = types.Part.from_function_response(
                        name=msg.name or "tool",
                        response=response_data,
                    )
                    fr_obj = getattr(part, "function_response", None)
                    if provider_id and fr_obj:
                        fr_obj.id = provider_id

                # Gemini represents function responses as user-role content.
                gemini_contents.append(types.Content(role="user", parts=[part]))

        # Prepare tools configuration
        function_declarations: list[Any] = []
        if tools:
            for tool_def in tools:
                fd = types.FunctionDeclaration(
                    name=tool_def.name,
                    description=tool_def.description,
                    parameters=_normalize_gemini_schema(tool_def.parameters),
                )
                function_declarations.append(fd)

        gemini_tools = (
            [types.Tool(function_declarations=function_declarations)]
            if function_declarations
            else None
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=gemini_contents,
                config=config,
            )
        except Exception:
            logger.exception("Erro ao chamar API do Gemini para o modelo '%s'", self._model)
            raise

        # Parse response into AgentMessage
        tool_calls: list[ToolCall] = []
        if getattr(response, "function_calls", None):
            for fc in response.function_calls:
                model_call_id = getattr(fc, "id", None)
                call_id = model_call_id or f"local_call_{uuid.uuid4().hex[:8]}"
                tool_calls.append(
                    ToolCall(
                        id=call_id,
                        name=fc.name,
                        arguments=dict(fc.args or {}),
                    )
                )

        text_content: str | None = None
        try:
            text_content = response.text.strip() if response.text else None
        except Exception:
            text_content = None

        return AgentMessage(
            role="assistant",
            content=text_content,
            tool_calls=tool_calls if tool_calls else None,
        )
