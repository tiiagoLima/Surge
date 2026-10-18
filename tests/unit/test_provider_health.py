"""Offline provider-neutral health, classification and secret-safety tests."""

import ast
import inspect
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from src.agent.adapters.outbound.provider_failure_classifier import (
    ProviderError,
    classify_provider_exception,
    sanitize_error_message,
)
from src.agent.domain import provider_health
from src.agent.domain.provider_health import (
    ProviderFailure,
    ProviderFailureKind,
    ProviderHealth,
    ProviderHealthPort,
    ProviderHealthStatus,
)


class StatusError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__("SDK payload with token=secret-value")


@pytest.mark.parametrize(
    ("signals", "kind", "retryable"),
    [
        ([401, 403, "PERMISSION_DENIED", "API_KEY_INVALID"], "authentication", False),
        (
            [404, "NOT_FOUND", "SURGE_GEMINI_API_KEY não configurada", "empty API key"],
            "configuration",
            False,
        ),
        ([429, "RESOURCE_EXHAUSTED", "quota"], "rate_limit", True),
        ([503, 500, "UNAVAILABLE"], "temporary_unavailable", True),
        # socket.timeout is an alias of TimeoutError on supported Python versions.
        ([504, "DEADLINE_EXCEEDED", TimeoutError()], "timeout", True),
        ([400, "INVALID_ARGUMENT", "BAD_REQUEST"], "invalid_request", False),
        (["unexpected"], "unknown", False),
    ],
)
def test_classification(signals: list[object], kind: str, retryable: bool) -> None:
    for signal in signals:
        if isinstance(signal, int):
            exc = StatusError(signal)
        elif isinstance(signal, Exception):
            exc = signal
        else:
            exc = RuntimeError(signal)
        failure = classify_provider_exception(exc)
        assert failure.kind == ProviderFailureKind(kind)
        assert failure.retryable is retryable
        assert "secret-value" not in failure.message


@pytest.mark.parametrize(
    "secret",
    [
        "AIza123456789_secret",
        "sk-secret-value",
        "Bearer secret-value",
        "api_key=secret-value",
        '"token": "secret-value"',
        "password=secret-value",
        "https://user:secret-value@example.com",
    ],
)
def test_sanitization(secret: str) -> None:
    sanitized = sanitize_error_message(secret)
    assert "secret-value" not in sanitized
    assert "AIza123456789_secret" not in sanitized
    assert "[REDACTED]" in sanitized


def test_exception_messages_never_echo_payloads() -> None:
    original = RuntimeError("private portfolio payload; token=secret-value")
    failure = classify_provider_exception(original)
    error = ProviderError(failure, original)
    assert error.original_exception is original
    assert error.failure is failure
    assert "private portfolio" not in str(error)
    assert "secret-value" not in str(error)


@pytest.mark.parametrize("attribute", ["status_code", "status", "response"])
def test_classification_reads_structured_status(attribute: str) -> None:
    exc = RuntimeError("opaque SDK failure")
    setattr(exc, attribute, SimpleNamespace(status_code=503) if attribute == "response" else 503)
    assert classify_provider_exception(exc).kind == ProviderFailureKind.TEMPORARY_UNAVAILABLE


def test_health_and_failure_are_immutable() -> None:
    failure = ProviderFailure(ProviderFailureKind.PERMANENT, "Safe message", False)
    health = ProviderHealth("gemini", "test-model", ProviderHealthStatus.UNAVAILABLE, failure)
    with pytest.raises(FrozenInstanceError):
        failure.retryable = True
    with pytest.raises(FrozenInstanceError):
        health.status = ProviderHealthStatus.AVAILABLE
    with pytest.raises(TypeError):
        ProviderHealthPort()


@pytest.mark.parametrize(
    ("kind", "message", "retryable"),
    [
        ("unknown", "safe", False),
        (None, "safe", False),
        (ProviderFailureKind.UNKNOWN, None, False),
        (ProviderFailureKind.UNKNOWN, " ", False),
        (ProviderFailureKind.UNKNOWN, "safe", 1),
    ],
)
def test_failure_validation(kind: object, message: object, retryable: object) -> None:
    with pytest.raises(ValueError):
        ProviderFailure(kind, message, retryable)


@pytest.mark.parametrize(
    ("provider", "model", "status", "failure"),
    [
        ("", "test", ProviderHealthStatus.AVAILABLE, None),
        (None, "test", ProviderHealthStatus.AVAILABLE, None),
        ("gemini", " ", ProviderHealthStatus.AVAILABLE, None),
        ("gemini", 1, ProviderHealthStatus.AVAILABLE, None),
        ("gemini", "test", "available", None),
        ("gemini", "test", ProviderHealthStatus.DEGRADED, "error"),
    ],
)
def test_health_validation(
    provider: object, model: object, status: object, failure: object
) -> None:
    with pytest.raises(ValueError):
        ProviderHealth(provider, model, status, failure)


def test_domain_uses_only_stdlib() -> None:
    for node in ast.walk(ast.parse(inspect.getsource(provider_health))):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module.split(".")[0] in sys.stdlib_module_names
