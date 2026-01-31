"""
Simple test for action.py TYPE_CHECKING coverage.
"""

import pytest


def test_action_module_coverage():
    """Test basic action module functionality to ensure coverage."""
    from causaliq_workflow.action import (
        ActionExecutionError,
        ActionValidationError,
        CausalIQAction,
    )

    # Test that all main classes can be imported and used
    assert CausalIQAction is not None
    assert ActionExecutionError is not None
    assert ActionValidationError is not None

    # Test exception creation
    exec_error = ActionExecutionError("Test execution error")
    assert str(exec_error) == "Test execution error"

    val_error = ActionValidationError("Test validation error")
    assert str(val_error) == "Test validation error"

    # Test that Action is abstract and can't be instantiated
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        CausalIQAction()

    # Test abstract run method exists
    assert hasattr(CausalIQAction, "run")

    # The TYPE_CHECKING import is hard to test directly since it only
    # runs during static type checking, not runtime. But importing
    # the module exercises most of the code paths.
    import causaliq_workflow.action

    assert hasattr(causaliq_workflow.action, "CausalIQAction")
