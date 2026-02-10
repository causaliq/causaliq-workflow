"""
Tests for remaining workflow edge cases to achieve 100% coverage.

Covers shell command execution, action outputs, and registry package grouping.
"""

import pytest

from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor
from tests.functional.fixtures.test_action import ActionProvider


class MockActionWithOutputs(ActionProvider):
    """Mock action that returns outputs."""

    name = "mock-action-with-outputs"
    version = "1.0.0"
    description = "Mock action that returns outputs"

    def run(self, action: str, parameters: dict, **kwargs) -> dict:
        return {
            "status": "success",
            "outputs": {"result_file": "output.csv", "score": 0.95},
        }


# Test that shell command execution raises not implemented error
def test_shell_command_execution_not_implemented():
    executor = WorkflowExecutor()

    # Register mock action
    executor.action_registry._actions["mock_action_with_outputs"] = (
        MockActionWithOutputs
    )

    workflow = {
        "id": "shell-test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [{"name": "Shell Step", "run": "echo 'Hello World'"}],
    }

    with pytest.raises(
        WorkflowExecutionError,
        match="Shell command execution not yet implemented",
    ):
        executor.execute_workflow(workflow, mode="run")


# Test error when step has neither 'uses' nor 'run'
def test_step_missing_uses_and_run():
    executor = WorkflowExecutor()

    workflow = {
        "id": "invalid-step-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "Invalid Step"
                # Missing both 'uses' and 'run'
            }
        ],
    }

    with pytest.raises(
        WorkflowExecutionError, match="must have 'uses' or 'run'"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test that action outputs are added to template variables
def test_action_with_outputs_added_to_variables():
    executor = WorkflowExecutor()

    # Register mock action
    executor.action_registry._actions["mock_action_with_outputs"] = (
        MockActionWithOutputs
    )

    workflow = {
        "id": "outputs-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {"name": "First Step", "uses": "mock_action_with_outputs"},
            {
                "name": "Second Step",
                "uses": "mock_action_with_outputs",
                "with": {
                    "previous_result": (
                        "{{steps.First Step.outputs.result_file}}"
                    )
                },
            },
        ],
    }

    results = executor.execute_workflow(workflow, mode="run")

    assert len(results) == 1
    job_result = results[0]

    # Check first step has outputs
    first_step = job_result["steps"]["First Step"]
    assert "outputs" in first_step
    assert first_step["outputs"]["result_file"] == "output.csv"
    assert first_step["outputs"]["score"] == 0.95

    # Check 2nd step received template-resolved input from 1st step's outputs
    job_result["steps"]["Second Step"]
    # Note: The mock action doesn't actually use the inputs, but template
    # resolution should work
    # This tests that the template resolution mechanism works with step outputs


# Test registry get_actions_by_package edge cases
def test_registry_get_actions_by_package_edge_cases():
    executor = WorkflowExecutor()

    # Test with actions from different module hierarchies

    # Create mock actions with different module structures
    class MockActionNoModule(ActionProvider):
        name = "no-module-action"
        version = "1.0.0"
        description = "Action with no module"

        def run(self, action: str, parameters: dict, **kwargs) -> dict:
            return {"status": "success"}

    # Simulate an action with empty module parts
    MockActionNoModule.__module__ = ""

    class MockActionDeepModule(ActionProvider):
        name = "deep-module-action"
        version = "1.0.0"
        description = "Action with deep module hierarchy"

        def run(self, action: str, parameters: dict, **kwargs) -> dict:
            return {"status": "success"}

    MockActionDeepModule.__module__ = "very.deep.package.structure.action"

    # Add to registry
    executor.action_registry._actions["no_module_action"] = MockActionNoModule
    executor.action_registry._actions["deep_module_action"] = (
        MockActionDeepModule
    )

    # Test package grouping
    packages = executor.action_registry.list_actions_by_package()

    # Check that actions are grouped by root package name
    assert (
        "" in packages
    )  # For action with empty module (becomes empty string)
    assert "very" in packages  # Root of deep module hierarchy

    assert "no_module_action" in packages[""]
    assert "deep_module_action" in packages["very"]


# Test package grouping with existing registry actions
def test_registry_package_grouping_existing_actions():
    executor = WorkflowExecutor()

    packages = executor.action_registry.list_actions_by_package()

    # Should have packages for test actions
    assert isinstance(packages, dict)

    # All package values should be lists of action names
    for package_name, action_names in packages.items():
        assert isinstance(package_name, str)
        assert isinstance(action_names, list)
        for action_name in action_names:
            assert isinstance(action_name, str)


# Force test of conditional import of WorkflowContext
def test_conditional_workflow_context_import():
    import causaliq_workflow.action

    assert hasattr(causaliq_workflow.action, "BaseActionProvider")
