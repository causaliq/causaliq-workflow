"""Unit tests for workflow provenance collection."""

import importlib.metadata

import pytest
from pytest_mock import MockerFixture

from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.provenance import (
    build_result_metadata,
    build_step_metadata,
    collect_environment,
    collect_step_provenance,
    execute_with_provenance,
    resolve_action_name,
    resolve_provider_version,
    split_action_metadata,
    utc_now,
    workflow_version,
)


def _action_class(version: str = "1.0.0") -> type:
    """Return a minimal provider class for provenance tests."""
    return type(
        "Action",
        (),
        {
            "name": "test-provider",
            "version": version,
            "supported_actions": {"test_action"},
        },
    )


# Test utc_now returns a parseable ISO timestamp.
def test_utc_now_returns_iso_timestamp() -> None:
    value = utc_now()
    assert value.endswith("+00:00")
    assert "T" in value


# Test collect_environment returns a copy of the environment mapping.
def test_collect_environment_returns_mapping(mocker: MockerFixture) -> None:
    mocker.patch(
        "causaliq_workflow.workflow.provenance._environment",
        return_value={"python": "3.12.4"},
    )
    assert collect_environment() == {"python": "3.12.4"}


# Test collect_environment returns None when collection fails.
def test_collect_environment_returns_none_on_error(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "causaliq_workflow.workflow.provenance._environment",
        side_effect=RuntimeError("no environment"),
    )
    assert collect_environment() is None


# Test collect_environment returns None for a non-mapping result.
def test_collect_environment_rejects_non_mapping(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "causaliq_workflow.workflow.provenance._environment",
        return_value=["not", "a", "mapping"],
    )
    assert collect_environment() is None


# Test resolve_provider_version prefers the provider class version.
def test_resolve_provider_version_uses_class_version() -> None:
    assert resolve_provider_version(_action_class("2.1.0"), "p") == "2.1.0"


# Test resolve_provider_version falls back to package metadata.
def test_resolve_provider_version_falls_back_to_metadata(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "causaliq_workflow.workflow.provenance.importlib.metadata.version",
        return_value="3.0.0",
    )
    assert resolve_provider_version(_action_class(""), "p") == "3.0.0"


# Test resolve_provider_version returns None when the package is unknown.
def test_resolve_provider_version_returns_none_when_missing(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "causaliq_workflow.workflow.provenance.importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError("p"),
    )
    assert resolve_provider_version(_action_class(""), "p") is None


# Test resolve_provider_version returns None for an invalid package name.
def test_resolve_provider_version_returns_none_for_invalid_name(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "causaliq_workflow.workflow.provenance.importlib.metadata.version",
        side_effect=ValueError("invalid"),
    )
    assert resolve_provider_version(_action_class(""), "p") is None


# Test workflow_version returns the package version.
def test_workflow_version_returns_package_version() -> None:
    from causaliq_workflow import __version__

    assert workflow_version() == __version__


# Test resolve_action_name prefers the explicit action.
def test_resolve_action_name_uses_explicit_name() -> None:
    assert resolve_action_name({"action": "run"}, _action_class()) == "run"


# Test resolve_action_name derives a single supported action.
def test_resolve_action_name_derives_single_action() -> None:
    assert resolve_action_name({}, _action_class()) == "test_action"


# Test resolve_action_name returns empty for several supported actions.
def test_resolve_action_name_returns_empty_for_several_actions() -> None:
    class Action:
        supported_actions = {"one", "two"}

    assert resolve_action_name({}, Action) == ""


# Test split_action_metadata returns structured blocks.
def test_split_action_metadata_returns_blocks() -> None:
    inputs, result = split_action_metadata(
        {"inputs": {"algorithm": "hc"}, "result": {"status": "ok"}}
    )
    assert inputs == {"algorithm": "hc"}
    assert result == {"status": "ok"}


# Test split_action_metadata places a flat mapping in result.
def test_split_action_metadata_treats_flat_mapping_as_result() -> None:
    inputs, result = split_action_metadata({"status": "ok"})
    assert inputs == {}
    assert result == {"status": "ok"}


# Test split_action_metadata handles a non-mapping value.
def test_split_action_metadata_handles_non_mapping() -> None:
    assert split_action_metadata(None) == ({}, {})


# Test collect_step_provenance records the execution window.
def test_collect_step_provenance_records_window() -> None:
    provenance = collect_step_provenance(
        _action_class(),
        "test-provider",
        {"action": "test_action"},
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:01+00:00",
        1.0,
        {"python": "3.12.4"},
    )
    assert provenance["provider"] == "test-provider"
    assert provenance["action"] == "test_action"
    assert provenance["provider_version"] == "1.0.0"
    assert provenance["duration_seconds"] == 1.0
    assert provenance["environment"] == {"python": "3.12.4"}


# Test build_step_metadata builds the version 2 envelope.
def test_build_step_metadata_builds_envelope() -> None:
    provenance = collect_step_provenance(
        _action_class(),
        "test-provider",
        {"action": "test_action"},
        "start",
        "finish",
        1.0,
        None,
    )
    metadata = build_step_metadata(provenance, {}, {"status": "ok"})
    assert metadata["result"] == {"status": "ok"}
    assert metadata["provenance"]["provider"] == "test-provider"


# Test build_result_metadata uses the action's structured metadata.
def test_build_result_metadata_uses_action_metadata() -> None:
    provenance = collect_step_provenance(
        _action_class(),
        "test-provider",
        {"action": "test_action"},
        "start",
        "finish",
        1.0,
        None,
    )
    step_result = {
        "_action_metadata": {
            "inputs": {"algorithm": "hc"},
            "result": {"status": "ok"},
        }
    }
    metadata = build_result_metadata(provenance, step_result)
    assert metadata["inputs"] == {"algorithm": "hc"}
    assert metadata["result"] == {"status": "ok"}


# Test execute_with_provenance executes and records the action.
def test_execute_with_provenance_executes_action(
    mocker: MockerFixture,
) -> None:
    registry = mocker.Mock()
    registry.execute_action.return_value = {
        "status": "success",
        "_action_metadata": {"status": "ok"},
    }
    registry.get_action_class.return_value = _action_class()
    step_result, provenance = execute_with_provenance(
        registry,
        "test-provider",
        {"action": "test_action"},
        None,
        None,
    )
    assert step_result["status"] == "success"
    assert provenance["action"] == "test_action"


# Test execute_with_provenance rejects an unresolved action name.
def test_execute_with_provenance_rejects_missing_action(
    mocker: MockerFixture,
) -> None:
    registry = mocker.Mock()
    registry.execute_action.return_value = {"status": "success"}
    registry.get_action_class.return_value = type(
        "Action",
        (),
        {"name": "p", "version": "1.0.0", "supported_actions": {"one", "two"}},
    )
    with pytest.raises(WorkflowExecutionError, match="action name"):
        execute_with_provenance(
            registry,
            "test-provider",
            {},
            None,
            None,
        )
