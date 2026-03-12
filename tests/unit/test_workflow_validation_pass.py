"""Unit tests for two-pass workflow validation.

Tests the validation pass that runs before workflow execution to catch
semantic errors like undefined filter variables.
"""

import pytest
from causaliq_core import ActionValidationError, CausalIQActionProvider

from causaliq_workflow.registry import ActionRegistry
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


class MockActionProvider(CausalIQActionProvider):
    """Mock action provider for testing validation."""

    name = "mock-provider"
    version = "1.0.0"
    supported_actions = {"test_action"}

    def _execute(self, action, parameters, mode, context, logger):
        """Execute mock action."""
        return ("success", {}, [])


class StrictActionProvider(CausalIQActionProvider):
    """Action provider that validates required parameters."""

    name = "strict-provider"
    version = "1.0.0"
    supported_actions = {"strict_action"}

    def validate_parameters(self, action, parameters):
        """Validate required_param is present."""
        super().validate_parameters(action, parameters)
        if "required_param" not in parameters:
            raise ActionValidationError("Missing required_param")

    def _execute(self, action, parameters, mode, context, logger):
        """Execute strict action."""
        return ("success", {}, [])


# Test validate_action_parameters skips actions without validation.
def test_validate_action_parameters_skips_no_method() -> None:
    """Actions without validate_parameters are skipped."""

    class LegacyAction:
        name = "legacy"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

    registry = ActionRegistry()
    registry._actions["legacy-action"] = LegacyAction

    # Should not raise - skips validation
    registry.validate_action_parameters(
        "legacy-action", {"action": "test", "param": "value"}
    )


# Test validate_action_parameters calls provider validation.
def test_validate_action_parameters_calls_provider() -> None:
    """Validation calls provider's validate_parameters method."""
    registry = ActionRegistry()
    registry._actions["mock-provider"] = MockActionProvider

    # Valid action - should pass
    registry.validate_action_parameters(
        "mock-provider", {"action": "test_action"}
    )


# Test validate_action_parameters raises on invalid action.
def test_validate_action_parameters_raises_invalid_action() -> None:
    """Invalid action name raises ActionValidationError."""
    registry = ActionRegistry()
    registry._actions["mock-provider"] = MockActionProvider

    with pytest.raises(ActionValidationError, match="does not support"):
        registry.validate_action_parameters(
            "mock-provider", {"action": "unknown_action"}
        )


# Test validate_action_parameters raises on missing required param.
def test_validate_action_parameters_raises_missing_param() -> None:
    """Missing required parameter raises ActionValidationError."""
    registry = ActionRegistry()
    registry._actions["strict-provider"] = StrictActionProvider

    with pytest.raises(ActionValidationError, match="Missing required_param"):
        registry.validate_action_parameters(
            "strict-provider", {"action": "strict_action"}
        )


# Test _validate_all_entries returns empty list for valid workflow.
def test_validate_all_entries_valid_workflow() -> None:
    """Valid workflow returns no validation errors."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockActionProvider

    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "test-step",
                "uses": "mock-provider",
                "with": {"action": "test_action"},
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert errors == []


# Test _validate_all_entries detects missing required params.
def test_validate_all_entries_missing_params() -> None:
    """Missing required params detected in validation pass."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-provider"] = StrictActionProvider

    workflow = {
        "matrix": {"network": ["asia", "alarm"]},
        "steps": [
            {
                "name": "strict-step",
                "uses": "strict-provider",
                "with": {"action": "strict_action"},
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 2  # One error per matrix combo
    assert all("Missing required_param" in e for e in errors)


# Test _validate_all_entries collects all errors across entries.
def test_validate_all_entries_collects_all_errors() -> None:
    """Validation collects ALL errors, not just first."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-provider"] = StrictActionProvider

    workflow = {
        "matrix": {"network": ["a", "b", "c"]},
        "steps": [
            {
                "name": "strict-step",
                "uses": "strict-provider",
                "with": {"action": "strict_action"},
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 3  # All 3 combos have errors


# Test execute_workflow raises on validation errors.
def test_execute_workflow_raises_on_validation_error(monkeypatch) -> None:
    """Execute fails if validation pass finds errors."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-provider"] = StrictActionProvider

    # Mock parse_workflow to skip file loading
    def mock_parse(path, mode="dry-run"):
        return {
            "matrix": {"x": [1]},
            "steps": [
                {
                    "name": "test",
                    "uses": "strict-provider",
                    "with": {"action": "strict_action"},
                }
            ],
        }

    monkeypatch.setattr(executor, "parse_workflow", mock_parse)

    workflow = mock_parse("/fake.yml")

    with pytest.raises(WorkflowExecutionError, match="Missing required_param"):
        executor.execute_workflow(workflow)


# Test validation skips steps without action providers.
def test_validate_all_entries_skips_missing_uses() -> None:
    """Steps without 'uses' are skipped in validation."""
    executor = WorkflowExecutor()

    workflow = {
        "matrix": {"x": [1]},
        "steps": [
            {"name": "shell-step", "run": "echo hello"},
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert errors == []


# Test validation catches steps without action name.
def test_validate_all_entries_catches_missing_action() -> None:
    """Steps without action name in 'with' now raise validation error."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockActionProvider

    workflow = {
        "matrix": {"x": [1]},
        "steps": [
            {
                "name": "no-action",
                "uses": "mock-provider",
                "with": {"other": "param"},
            },
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 1
    assert "Missing 'action' parameter" in errors[0]


# Test validation with empty matrix (single job).
def test_validate_all_entries_empty_matrix() -> None:
    """Empty matrix results in single validation job."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-provider"] = StrictActionProvider

    workflow = {
        "steps": [
            {
                "name": "test",
                "uses": "strict-provider",
                "with": {"action": "strict_action"},
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 1  # Single job with missing param


# Test successful validation allows execution to proceed.
def test_execute_workflow_proceeds_after_valid() -> None:
    """Execution proceeds when validation passes."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockActionProvider

    workflow = {
        "matrix": {"x": [1]},
        "steps": [
            {
                "name": "test",
                "uses": "mock-provider",
                "with": {"action": "test_action"},
            }
        ],
    }

    # Dry-run should succeed (validation passes)
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1


# Test ActionRegistryError is re-raised from validate_action_parameters.
def test_validate_action_parameters_reraises_registry_error() -> None:
    """ActionRegistryError from get_action_class is re-raised."""
    from causaliq_workflow.registry import ActionRegistryError

    registry = ActionRegistry()
    # No actions registered - will raise ActionRegistryError

    with pytest.raises(ActionRegistryError, match="not found"):
        registry.validate_action_parameters(
            "nonexistent-provider", {"action": "test"}
        )


# Test generic Exception wrapped in ActionValidationError.
def test_validate_action_parameters_wraps_exception() -> None:
    """Generic exceptions are wrapped in ActionValidationError."""

    class BrokenProvider(CausalIQActionProvider):
        name = "broken"
        supported_actions = {"broken_action"}

        def validate_parameters(self, action, parameters):
            raise RuntimeError("Something went wrong")

        def _execute(self, action, parameters, mode, context, logger):
            return ("success", {}, [])

    registry = ActionRegistry()
    registry._actions["broken-provider"] = BrokenProvider

    with pytest.raises(ActionValidationError, match="Something went wrong"):
        registry.validate_action_parameters(
            "broken-provider", {"action": "broken_action"}
        )


# Test _deduplicate_errors keeps unmatched errors as-is.
def test_deduplicate_errors_keeps_unmatched_errors() -> None:
    """Tests lines 1189-1190 in workflow.py - unmatched errors kept."""
    executor = WorkflowExecutor()

    # Errors that don't match the "Step 'name': message" pattern
    errors = [
        "Some random error without step prefix",
        "Another unmatched error",
        "Some random error without step prefix",  # Duplicate
    ]

    result = executor._deduplicate_errors(errors)

    # Should keep unmatched errors (deduplicated)
    assert "Some random error without step prefix" in result
    assert "Another unmatched error" in result
    # Duplicates should be removed
    assert result.count("Some random error without step prefix") == 1
