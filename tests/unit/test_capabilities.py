"""Offline tests for capability declarations and composition-root builders."""

import ast
import inspect
import sys
from dataclasses import FrozenInstanceError, fields
from itertools import product
from types import SimpleNamespace

import pytest

from src import main as cli
from src.agent.domain import capabilities
from src.agent.domain.capabilities import (
    CapabilityDefinition,
    CapabilityRegistry,
    CapabilityRequirements,
    RequirementLevel,
    RuntimeAvailability,
)


def test_requirements_default_to_no_resources() -> None:
    requirements = CapabilityRequirements()
    assert (requirements.llm, requirements.network, requirements.storage) == (
        RequirementLevel.NOT_REQUIRED,
        RequirementLevel.NOT_REQUIRED,
        RequirementLevel.NOT_REQUIRED,
    )
    assert RuntimeAvailability() == RuntimeAvailability(False, False, False)


def test_requirement_level_values() -> None:
    assert {level.value for level in RequirementLevel} == {"not_required", "optional", "required"}
    assert all(isinstance(level, str) for level in RequirementLevel)
    with pytest.raises(ValueError):
        RequirementLevel("sim")


@pytest.mark.parametrize("field_name", ["llm", "network", "storage"])
@pytest.mark.parametrize(
    "value", ["required", "optional", "not_required", True, False, 1, None, {}]
)
def test_requirements_reject_non_enum_values(field_name: str, value: object) -> None:
    with pytest.raises(ValueError, match=field_name):
        CapabilityRequirements(**{field_name: value})


@pytest.mark.parametrize("field_name", ["llm", "network", "storage"])
@pytest.mark.parametrize("value", ["sim", 1, 0, None, 1.0, [], {}, RequirementLevel.REQUIRED])
def test_availability_rejects_non_boolean_values(field_name: str, value: object) -> None:
    with pytest.raises(ValueError, match=field_name):
        RuntimeAvailability(**{field_name: value})


@pytest.mark.parametrize("requirements", [None, {}, "storage", True, 1])
def test_definition_rejects_invalid_requirements(requirements: object) -> None:
    with pytest.raises(ValueError, match="CapabilityRequirements"):
        CapabilityDefinition("portfolio.get_holdings", requirements)


def test_capability_requirements_have_only_provider_neutral_fields() -> None:
    assert {field.name for field in fields(CapabilityRequirements)} == {"llm", "network", "storage"}
    assert {field.name for field in fields(RuntimeAvailability)} == {"llm", "network", "storage"}


def test_capability_domain_imports_only_standard_library() -> None:
    tree = ast.parse(inspect.getsource(capabilities))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in sys.stdlib_module_names
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "Relative imports could introduce adapter/provider dependencies"
            assert node.module is not None
            assert node.module.split(".")[0] in sys.stdlib_module_names


def test_definitions_and_requirements_are_immutable() -> None:
    requirements = CapabilityRequirements(storage=RequirementLevel.REQUIRED)
    capability = CapabilityDefinition("portfolio.get_holdings", requirements)
    with pytest.raises(FrozenInstanceError):
        requirements.llm = RequirementLevel.OPTIONAL
    available = RuntimeAvailability()
    with pytest.raises(FrozenInstanceError):
        available.llm = True
    with pytest.raises(FrozenInstanceError):
        capability.id = "changed"
    with pytest.raises(FrozenInstanceError):
        capability.requirements = CapabilityRequirements()


@pytest.mark.parametrize("capability_id", ["", " ", "\t\n", None, 42, False])
def test_definition_rejects_invalid_ids(capability_id: str) -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        CapabilityDefinition(capability_id, CapabilityRequirements())


def test_registry_registers_and_returns_independent_lists() -> None:
    registry = CapabilityRegistry()
    assert registry.list_capabilities() == []
    assert registry.get("unknown") is None
    first = CapabilityDefinition(
        "portfolio.get_holdings", CapabilityRequirements(storage=RequirementLevel.REQUIRED)
    )
    second = CapabilityDefinition(
        "agent.ask", CapabilityRequirements(llm=RequirementLevel.REQUIRED)
    )
    registry.register(first)
    registry.register(second)
    assert registry.get(first.id) == first
    assert registry.list_capabilities() == [first, second]
    registry.list_capabilities().clear()
    assert registry.list_capabilities() == [first, second]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(CapabilityDefinition(first.id, CapabilityRequirements()))
    assert registry.get(first.id) == first


def test_registry_validates_id_on_registration() -> None:
    # Exercise the registry guard even for an object bypassing dataclass validation.
    capability = object.__new__(CapabilityDefinition)
    object.__setattr__(capability, "id", "")
    object.__setattr__(capability, "requirements", CapabilityRequirements())
    registry = CapabilityRegistry()
    with pytest.raises(ValueError, match="non-empty string"):
        registry.register(capability)
    assert registry.list_capabilities() == []


@pytest.mark.parametrize("required", list(product(RequirementLevel, repeat=3)))
@pytest.mark.parametrize("available", list(product([False, True], repeat=3)))
def test_eligibility_matches_each_required_resource(
    required: tuple[RequirementLevel, RequirementLevel, RequirementLevel],
    available: tuple[bool, bool, bool],
) -> None:
    registry = CapabilityRegistry()
    registry.register(CapabilityDefinition("test", CapabilityRequirements(*required)))
    expected = all(
        needed != RequirementLevel.REQUIRED or present
        for needed, present in zip(required, available, strict=True)
    )
    expected_full = all(
        needed == RequirementLevel.NOT_REQUIRED or present
        for needed, present in zip(required, available, strict=True)
    )
    assert registry.is_eligible("test", RuntimeAvailability(*available)) is expected
    assert registry.is_fully_supported("test", RuntimeAvailability(*available)) is expected_full


def test_eligibility_rejects_unknown_capability() -> None:
    with pytest.raises(KeyError, match="unknown"):
        CapabilityRegistry().is_eligible("unknown", RuntimeAvailability())
    with pytest.raises(KeyError, match="unknown"):
        CapabilityRegistry().is_fully_supported("unknown", RuntimeAvailability())


def test_build_registry_needs_neither_settings_nor_agent_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden() -> None:
        pytest.fail("Building declarations must not read settings or construct adapters/runtime")

    monkeypatch.setattr(cli, "get_settings", forbidden)
    monkeypatch.setattr(cli, "build_agent_runtime", forbidden)
    monkeypatch.setattr(cli, "_build_ports", forbidden)
    registry = cli.build_capability_registry()
    assert {item.id: item.requirements for item in registry.list_capabilities()} == {
        "portfolio.get_holdings": CapabilityRequirements(storage=RequirementLevel.REQUIRED),
        "portfolio.manage": CapabilityRequirements(
            network=RequirementLevel.REQUIRED, storage=RequirementLevel.REQUIRED
        ),
        "memory.manage": CapabilityRequirements(storage=RequirementLevel.REQUIRED),
        "investment.scan_portfolio": CapabilityRequirements(
            llm=RequirementLevel.OPTIONAL,
            network=RequirementLevel.REQUIRED,
            storage=RequirementLevel.REQUIRED,
        ),
        "agent.ask": CapabilityRequirements(
            llm=RequirementLevel.REQUIRED,
            network=RequirementLevel.REQUIRED,
            storage=RequirementLevel.REQUIRED,
        ),
    }


@pytest.mark.parametrize("api_key", ["", "offline-test-key"])
def test_runtime_eligibility_with_and_without_llm(
    monkeypatch: pytest.MonkeyPatch, api_key: str
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(gemini_api_key=api_key))
    available = cli.get_runtime_capabilities()
    assert available == RuntimeAvailability(llm=bool(api_key), network=True, storage=True)
    registry = cli.build_capability_registry()
    for capability_id in ("portfolio.get_holdings", "portfolio.manage", "memory.manage"):
        assert registry.is_eligible(capability_id, available)
    assert registry.is_eligible("agent.ask", available) is bool(api_key)
    assert registry.is_fully_supported("agent.ask", available) is bool(api_key)
    assert registry.is_eligible("investment.scan_portfolio", available)
    assert registry.is_fully_supported("investment.scan_portfolio", available) is bool(api_key)


def test_portfolio_manage_requires_network_but_not_llm() -> None:
    registry = cli.build_capability_registry()
    assert not registry.is_eligible("portfolio.manage", RuntimeAvailability(storage=True))
    assert registry.is_eligible("portfolio.manage", RuntimeAvailability(network=True, storage=True))
    assert registry.is_eligible("portfolio.get_holdings", RuntimeAvailability(storage=True))


@pytest.mark.parametrize("llm", [False, True])
def test_scan_is_ineligible_without_network(llm: bool) -> None:
    registry = cli.build_capability_registry()
    available = RuntimeAvailability(llm=llm, storage=True)
    assert not registry.is_eligible("investment.scan_portfolio", available)
    assert not registry.is_fully_supported("investment.scan_portfolio", available)


def test_deterministic_capability_executes_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from datetime import UTC, datetime

    from src.agent.adapters.tools.portfolio_tools import make_get_portfolio_holdings_handler
    from src.investments.domain.models import Holding
    from tests.unit.test_portfolio_tools import FakePortfolioUseCase

    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(gemini_api_key=""))
    available = cli.get_runtime_capabilities()
    registry = cli.build_capability_registry()

    assert registry.is_eligible("portfolio.get_holdings", available)

    # Prove effective execution of the deterministic capability without API key or model
    use_case = FakePortfolioUseCase(
        [
            Holding(
                ticker="PETR4.SA",
                quantity=100.0,
                avg_price=30.0,
                currency="BRL",
                added_at=datetime.now(UTC),
            )
        ]
    )
    handler = make_get_portfolio_holdings_handler(use_case)
    payload = json.loads(handler({}))

    assert payload["total_positions"] == 1
    assert payload["holdings"][0]["ticker"] == "PETR4.SA"
    assert payload["holdings"][0]["total_cost"] == 3000.0
