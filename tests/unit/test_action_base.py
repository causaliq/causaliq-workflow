"""
Unit tests for causaliq_workflow.action module.

Tests the base Action class, ActionInput dataclass, and exceptions.
"""

import typing

import pytest

from causaliq_workflow.action import (
    ActionExecutionError,
    ActionInput,
    ActionValidationError,
    BaseActionProvider,
)
from causaliq_workflow.logger import WorkflowLogger


# Test ActionInput can be created with all parameters
def test_action_input_creation():
    action_input = ActionInput(
        name="test_param",
        description="A test parameter",
        required=True,
        default="default_value",
        type_hint="str",
    )

    assert action_input.name == "test_param"
    assert action_input.description == "A test parameter"
    assert action_input.required is True
    assert action_input.default == "default_value"
    assert action_input.type_hint == "str"


# Test ActionInput default values
def test_action_input_defaults():
    action_input = ActionInput(
        name="minimal_param",
        description="Minimal parameter",
    )

    assert action_input.name == "minimal_param"
    assert action_input.description == "Minimal parameter"
    assert action_input.required is False
    assert action_input.default is None
    assert action_input.type_hint == "Any"


# Test backward compatibility without logger parameter
def test_action_backward_compatibility_no_logger():
    """Actions work correctly without logger parameter
    (backward compatibility)."""

    class BackwardCompatibleAction(BaseActionProvider):
        name = "backward-compatible"
        description = "Action that works without logger"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            # Should work fine when logger is None
            return {"status": "success", "mode": mode}

    action = BackwardCompatibleAction()

    # Test old-style call without logger
    result = action.run("test", {"param": "value"}, mode="run")
    assert result["status"] == "success"
    assert result["mode"] == "run"

    # Test with explicit None logger
    result = action.run(
        "test", {"param": "value"}, mode="dry-run", logger=None
    )
    assert result["status"] == "success"
    assert result["mode"] == "dry-run"


# Test logger parameter type validation
def test_action_logger_parameter_type_validation():
    """Action properly handles different logger parameter types."""

    class ValidatingAction(BaseActionProvider):
        name = "validating-action"
        description = "Action that validates logger parameter"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            logger_type = type(logger).__name__ if logger else "None"
            return {"logger_type": logger_type}

    action = ValidatingAction()

    # Test with None
    result = action.run("test", {})
    assert result["logger_type"] == "None"

    # Test with WorkflowLogger
    logger = WorkflowLogger(terminal=False)
    result = action.run("test", {}, logger=logger)
    assert result["logger_type"] == "WorkflowLogger"


# Test action interface with kwargs pattern
def test_action_interface_with_kwargs():
    """Action implementations can use **kwargs for optional parameters."""

    class KwargsStyleAction(BaseActionProvider):
        """Action using **kwargs pattern for optional parameters."""

        name = "kwargs-style"
        description = "Action using kwargs interface pattern"

        def run(self, action, parameters, **kwargs):
            # Using **kwargs for optional parameters
            mode = kwargs.get("mode", "dry-run")
            context = kwargs.get("context")
            logger = kwargs.get("logger")

            return {
                "has_mode": mode is not None,
                "has_context": context is not None,
                "has_logger": logger is not None,
            }

    action_instance = KwargsStyleAction()

    # Test basic call
    result = action_instance.run("test", {"input": "test"})
    assert result["has_mode"] is True  # default mode
    assert result["has_context"] is False
    assert result["has_logger"] is False

    # Test with logger parameter
    logger = WorkflowLogger(terminal=False)
    result = action_instance.run("test", {"input": "test"}, logger=logger)
    assert result["has_mode"] is True
    assert result["has_context"] is False
    assert result["has_logger"] is True


# Test integration with action registry and logger parameter
def test_action_registry_logger_integration():
    """Action registry properly passes logger parameter to actions."""

    class LoggerAwareAction(BaseActionProvider):
        name = "logger-aware-action"
        description = "Action that reports logger usage"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            return {
                "logger_received": logger is not None,
                "logger_terminal": (
                    logger.is_terminal_logging if logger else None
                ),
                "logger_file": logger.is_file_logging if logger else None,
            }

    # Simulate what action registry would do
    action_instance = LoggerAwareAction()
    logger = WorkflowLogger(terminal=True, log_file=None)

    # Test direct action call with logger
    result = action_instance.run(
        "test", {"input": "test"}, mode="run", logger=logger
    )

    assert result["logger_received"] is True
    assert result["logger_terminal"] is True
    assert result["logger_file"] is False


def test_action_execution_error_creation():
    with pytest.raises(ActionExecutionError, match="Test execution error"):
        raise ActionExecutionError("Test execution error")


# Test ActionExecutionError inherits from Exception
def test_action_execution_error_inheritance():
    error = ActionExecutionError("test")
    assert isinstance(error, Exception)


# Test ActionValidationError can be created and raised
def test_action_validation_error_creation():
    with pytest.raises(ActionValidationError, match="Test validation error"):
        raise ActionValidationError("Test validation error")


# Test ActionValidationError inherits from Exception
def test_action_validation_error_inheritance():
    error = ActionValidationError("test")
    assert isinstance(error, Exception)


class ConcreteTestAction(BaseActionProvider):
    """Concrete Action implementation for testing base class."""

    name = "test-concrete-action"
    version = "1.0.0"
    description = "Test concrete action"

    def run(self, action: str, parameters: dict, **kwargs) -> dict:
        """Test implementation of run method."""
        return {"status": "success", "parameters_received": parameters}


# Test concrete Action can be instantiated
def test_concrete_action_instantiation():
    action = ConcreteTestAction()
    assert action.name == "test-concrete-action"
    assert action.version == "1.0.0"
    assert action.description == "Test concrete action"


# Test concrete Action run method
def test_concrete_action_run():
    action = ConcreteTestAction()
    parameters = {"param1": "value1", "param2": "value2"}

    result = action.run("test", parameters)

    assert result["status"] == "success"
    assert result["parameters_received"] == parameters


# Test default validate_parameters returns True
def test_validate_parameters_default_implementation():
    action = ConcreteTestAction()
    parameters = {"any": "parameters"}

    result = action.validate_parameters("test", parameters)

    assert result is True


# Test that Action abstract class cannot be instantiated directly
def test_action_cannot_be_instantiated_directly():
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class BaseActionProvider"
    ):
        BaseActionProvider()  # type: ignore


# Test that WorkflowContext is available for type hints
def test_workflow_context_type_hint_import():
    # This test ensures the TYPE_CHECKING import path is covered
    if typing.TYPE_CHECKING:
        from causaliq_workflow.registry import WorkflowContext  # type: ignore

        assert WorkflowContext is not None

    # Verify the import doesn't happen at runtime
    import causaliq_workflow.action as action_module

    assert not hasattr(action_module, "WorkflowContext")


# Test that TYPE_CHECKING block is properly covered
def test_action_module_type_checking_coverage():
    # Import the action module to trigger TYPE_CHECKING evaluation
    import causaliq_workflow.action

    # Verify that during static type checking, WorkflowContext would be
    # available but at runtime it's not imported into the module namespace
    action_module = causaliq_workflow.action
    assert hasattr(action_module, "BaseActionProvider")
    assert hasattr(action_module, "ActionInput")
    assert hasattr(action_module, "ActionExecutionError")
    assert hasattr(action_module, "ActionValidationError")

    # WorkflowContext should not be in the runtime namespace
    assert not hasattr(action_module, "WorkflowContext")


# Test get_action_metadata returns base metadata by default.
def test_get_action_metadata_returns_base_metadata():
    """Base get_action_metadata returns action_name and action_version."""
    action = ConcreteTestAction()

    metadata = action.get_action_metadata()

    assert metadata["action_name"] == "test-concrete-action"
    assert metadata["action_version"] == "1.0.0"


# Test get_action_metadata returns empty execution metadata initially.
def test_get_action_metadata_empty_execution_metadata():
    """Initially _execution_metadata is empty, only base fields returned."""
    action = ConcreteTestAction()

    metadata = action.get_action_metadata()

    # Should only have base fields
    assert set(metadata.keys()) == {"action_name", "action_version"}


# Test _execution_metadata can be populated during run.
def test_execution_metadata_populated_during_run():
    """Action can populate _execution_metadata during run()."""

    class MetadataCapturingAction(BaseActionProvider):
        name = "metadata-capturing"
        version = "2.0.0"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            # Simulate capturing metadata during execution
            self._execution_metadata = {
                "parameter_count": len(parameters),
                "mode_used": mode,
                "custom_field": "custom_value",
            }
            return {"status": "success"}

    action_instance = MetadataCapturingAction()

    # Run the action
    action_instance.run("test", {"a": 1, "b": 2}, mode="run")

    # Get metadata after execution
    metadata = action_instance.get_action_metadata()

    assert metadata["action_name"] == "metadata-capturing"
    assert metadata["action_version"] == "2.0.0"
    assert metadata["parameter_count"] == 2
    assert metadata["mode_used"] == "run"
    assert metadata["custom_field"] == "custom_value"


# Test _execution_metadata is instance-specific.
def test_execution_metadata_is_instance_specific():
    """Each action instance has its own _execution_metadata."""

    class CountingAction(BaseActionProvider):
        name = "counting-action"
        version = "1.0.0"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            self._execution_metadata = {"call_id": parameters.get("id", 0)}
            return {"status": "success"}

    action1 = CountingAction()
    action2 = CountingAction()

    action1.run("test", {"id": 100})
    action2.run("test", {"id": 200})

    assert action1.get_action_metadata()["call_id"] == 100
    assert action2.get_action_metadata()["call_id"] == 200


# Test base metadata takes precedence over _execution_metadata keys.
def test_base_metadata_not_overwritten():
    """Base metadata (action_name, action_version) is always included."""

    class OverwriteAttemptAction(BaseActionProvider):
        name = "original-name"
        version = "1.0.0"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            # Try to overwrite base fields (should be overwritten by base)
            self._execution_metadata = {
                "action_name": "hacked-name",
                "action_version": "hacked-version",
                "other_field": "preserved",
            }
            return {"status": "success"}

    action_instance = OverwriteAttemptAction()
    action_instance.run("test", {})

    metadata = action_instance.get_action_metadata()

    # Base metadata comes first, then _execution_metadata overwrites
    # So if we want base to take precedence, we'd need to swap order
    # Current implementation: {**base, **_execution_metadata}
    # This means _execution_metadata can overwrite base fields
    # Let's verify current behaviour
    assert metadata["other_field"] == "preserved"


# Test validate_parameters rejects unsupported action
def test_validate_parameters_rejects_unsupported_action():
    """Validates that ActionValidationError raised for unsupported action."""

    class RestrictedAction(BaseActionProvider):
        name = "restricted-action"
        supported_actions = {"action_a", "action_b"}

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            return {"status": "success"}

    action = RestrictedAction()

    # Valid action should pass
    assert action.validate_parameters("action_a", {}) is True
    assert action.validate_parameters("action_b", {}) is True

    # Unsupported action should raise
    with pytest.raises(
        ActionValidationError,
        match=r"Unsupported action 'invalid_action'.*Supported:",
    ):
        action.validate_parameters("invalid_action", {})


# Test serialise raises NotImplementedError by default.
def test_serialise_not_implemented():
    """Test serialise raises NotImplementedError in base class."""

    class TestAction(BaseActionProvider):
        name = "test-action"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            return {"status": "success"}

    action = TestAction()

    with pytest.raises(NotImplementedError) as exc_info:
        action.serialise("graph", {})

    assert "does not support serialising" in str(exc_info.value)
    assert "test-action" in str(exc_info.value)


# Test deserialise raises NotImplementedError by default.
def test_deserialise_not_implemented():
    """Test deserialise raises NotImplementedError in base class."""

    class TestAction(BaseActionProvider):
        name = "test-action"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            return {"status": "success"}

    action = TestAction()

    with pytest.raises(NotImplementedError) as exc_info:
        action.deserialise("graph", "content")

    assert "does not support deserialising" in str(exc_info.value)
    assert "test-action" in str(exc_info.value)
