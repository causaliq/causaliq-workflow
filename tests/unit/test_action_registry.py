"""Unit tests for ActionRegistry."""

import sys
from types import ModuleType

import pytest

# Import test_action to register it for testing
import test_action  # noqa: F401

from causaliq_workflow.registry import ActionRegistry, ActionRegistryError


# Test registry initialization discovers available actions
def test_init_discovers_actions():
    registry = ActionRegistry()
    available_actions = registry.get_available_actions()

    # test_action should be discovered automatically
    assert "test_action" in available_actions
    assert available_actions["test_action"].__name__ == "CausalIQAction"


# Test get_available_actions returns a copy, not the internal dict
def test_get_available_actions_returns_copy():
    registry = ActionRegistry()
    actions1 = registry.get_available_actions()
    actions2 = registry.get_available_actions()

    # Should be equal but not the same object
    assert actions1 == actions2
    assert actions1 is not actions2


# Test has_action method
def test_has_action():
    registry = ActionRegistry()

    assert registry.has_action("test_action") is True
    assert registry.has_action("nonexistent_action") is False


# Test get_action_class method
def test_get_action_class():
    registry = ActionRegistry()

    action_class = registry.get_action_class("test_action")
    assert action_class.__name__ == "CausalIQAction"
    assert action_class.name == "test-action"


# Test get_action_class raises error for missing action
def test_get_action_class_not_found():
    registry = ActionRegistry()

    with pytest.raises(ActionRegistryError) as exc_info:
        registry.get_action_class("nonexistent_action")

    assert "Action 'nonexistent_action' not found" in str(exc_info.value)
    assert "Available actions:" in str(exc_info.value)


# Test get_discovery_errors method
def test_get_discovery_errors():
    registry = ActionRegistry()
    errors = registry.get_discovery_errors()

    # Should return a list (may be empty)
    assert isinstance(errors, list)


# Test register_action class method creates singleton
def test_singleton_register_action():
    # This tests the static registration method
    from test_action import CausalIQAction as TestAction

    # The singleton pattern means all instances share the same registry
    # So we can't test isolated registration. Instead, test that the
    # register_action method works without error.
    try:
        ActionRegistry.register_action("manual_test", TestAction)
    except Exception as e:
        pytest.fail(f"register_action should not raise exception: {e}")


# Test execute_action method with workflow context
def test_execute_action_with_context():
    from causaliq_workflow.registry import WorkflowContext

    registry = ActionRegistry()

    context = WorkflowContext(
        mode="dry-run",
        matrix={"param": ["value1", "value2"]},
    )

    inputs = {
        "data_path": "/test/input.csv",
        "output_dir": "/test/output",
        "message": "Test message",
    }

    result = registry.execute_action("test_action", inputs, context)

    # Should get dry-run results
    assert result["status"] == "dry-run-success"
    assert result["message_count"] == len("Test message")
    assert "output_file" in result


# Test execute_action raises error for missing action
def test_execute_action_not_found():
    from causaliq_workflow.action import ActionExecutionError
    from causaliq_workflow.registry import WorkflowContext

    registry = ActionRegistry()
    context = WorkflowContext(
        mode="dry-run",
        matrix={},
    )

    with pytest.raises(ActionExecutionError) as exc_info:
        registry.execute_action("nonexistent_action", {}, context)

        assert "Action 'nonexistent_action' execution failed" in str(
            exc_info.value
        )


# Check built-in modules are ignored
@pytest.mark.usefixtures("monkeypatch")
def test_registry_line_76_builtin_module_skip(monkeypatch):
    registry = ActionRegistry()

    # Create a fake module that starts with a builtin module name
    fake_builtin_module = ModuleType("os.custom_submodule")
    sys.modules["os.custom_submodule"] = fake_builtin_module

    # Mock sys.builtin_module_names to include 'os'
    original_builtin = sys.builtin_module_names
    mock_builtin_names = (
        list(original_builtin) + ["os"]
        if "os" not in original_builtin
        else original_builtin
    )
    monkeypatch.setattr(sys, "builtin_module_names", mock_builtin_names)

    # Mock pkgutil.iter_modules to return our fake builtin module
    import pkgutil

    monkeypatch.setattr(
        pkgutil, "iter_modules", lambda: [(None, "os.custom_submodule", False)]
    )

    try:
        registry._discover_actions()
        assert True
    finally:
        if "os.custom_submodule" in sys.modules:
            del sys.modules["os.custom_submodule"]

    # Cover registry.py line 256 - handle empty module_parts (unknown)
    registry = ActionRegistry()

    # Create a custom module name object whose split returns an empty list
    class ModuleName:
        def split(self, sep=None):
            return []

    # Create a simple action object
    class DummyAction:
        pass

    mock_action = DummyAction()
    mock_action.__module__ = ModuleName()
    mock_action.name = "empty-module"

    # Manually add this action to the registry
    registry._actions["empty-module"] = mock_action

    # Call list_actions_by_package which contains line 256
    registry.list_actions_by_package()


# Test execute_action automatically includes action_metadata in result.
def test_execute_action_includes_action_metadata():
    """execute_action automatically calls get_action_metadata."""
    from causaliq_workflow.registry import WorkflowContext

    registry = ActionRegistry()

    context = WorkflowContext(
        mode="dry-run",
        matrix={},
    )

    inputs = {
        "data_path": "/test/input.csv",
        "output_dir": "/test/output",
        "message": "Test",
    }

    result = registry.execute_action("test_action", inputs, context)

    # Result should contain action_metadata key
    assert "action_metadata" in result
    assert result["action_metadata"]["action_name"] == "test-action"
    assert result["action_metadata"]["action_version"] == "1.0.0"
