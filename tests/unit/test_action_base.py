"""
Unit tests for causaliq_workflow.action module.

Tests the base Action class, ActionInput dataclass, and exceptions.
"""

import pytest
from causaliq_core import (
    ActionExecutionError,
    ActionInput,
    ActionValidationError,
    CausalIQActionProvider,
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

    class BackwardCompatibleAction(CausalIQActionProvider):
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

    class ValidatingAction(CausalIQActionProvider):
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

    class KwargsStyleAction(CausalIQActionProvider):
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

    class LoggerAwareAction(CausalIQActionProvider):
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


class ConcreteTestAction(CausalIQActionProvider):
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


# Test that Action abstract class cannot be instantiated directly
def test_action_cannot_be_instantiated_directly():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        CausalIQActionProvider()  # type: ignore


# Test compress raises NotImplementedError by default.
def test_compress_not_implemented():
    """Test compress raises NotImplementedError in base class."""
    from causaliq_core import TokenCache

    class TestAction(CausalIQActionProvider):
        name = "test-action"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            return {"status": "success"}

    action = TestAction()

    with TokenCache(":memory:") as cache:
        with pytest.raises(NotImplementedError) as exc_info:
            action.compress("graph", "{}", cache)

    assert "does not support compressing" in str(exc_info.value)
    assert "test-action" in str(exc_info.value)


# Test decompress raises NotImplementedError by default.
def test_decompress_not_implemented():
    """Test decompress raises NotImplementedError in base class."""
    from causaliq_core import TokenCache

    class TestAction(CausalIQActionProvider):
        name = "test-action"

        def run(
            self, action, parameters, mode="dry-run", context=None, logger=None
        ):
            return {"status": "success"}

    action = TestAction()

    with TokenCache(":memory:") as cache:
        with pytest.raises(NotImplementedError) as exc_info:
            action.decompress("graph", b"content", cache)

    assert "does not support decompressing" in str(exc_info.value)
    assert "test-action" in str(exc_info.value)
