"""
Functional tests for WorkflowExecutor that access the filesystem.
Moved from unit test module for proper separation.
"""

import pytest

from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


# Pytest fixture for executor setup
@pytest.fixture
def executor():
    executor = WorkflowExecutor()
    from tests.functional.fixtures.test_action import ActionProvider

    class MockWorkflowAction(ActionProvider):
        name = "mock-workflow-action"
        version = "1.0.0"
        description = "Mock action for workflow testing"

        def run(self, inputs: dict, **kwargs) -> dict:
            mode = kwargs.get("mode", "run")
            context = kwargs.get("context")
            result = {
                "status": "validated" if mode == "dry-run" else "executed",
                "mode": mode,
                "inputs": inputs,
            }
            if context:
                result["context_mode"] = context.mode
            return result

    class MockFailingAction(ActionProvider):
        name = "mock-failing-action"
        version = "1.0.0"
        description = "Mock action that always fails"

        def run(self, inputs: dict, **kwargs) -> dict:
            raise Exception("Mock action failure")

    executor.action_registry._actions["mock_workflow_action"] = (
        MockWorkflowAction
    )
    executor.action_registry._actions["mock_failing_action"] = (
        MockFailingAction
    )
    return executor


# Test parsing workflow integration with validation


def test_parse_workflow_integration(executor):
    workflow_path = "tests/data/functional/workflow/valid_workflow.yml"
    result = executor.parse_workflow(workflow_path, mode="dry-run")
    assert result["id"] == "test-001"
    assert "asia" in result["matrix"]["dataset"]


# Test parsing workflow with validation failure


def test_parse_workflow_validation_failure(executor):
    workflow_path = "tests/data/functional/workflow/invalid_workflow.yml"
    with pytest.raises(
        WorkflowExecutionError, match="Unexpected error parsing workflow"
    ):
        executor.parse_workflow(workflow_path, mode="run")
