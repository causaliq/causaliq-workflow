"""Shared fixtures for unit tests."""

import pytest
from causaliq_core import ActionExecutionError, ActionResult

from causaliq_workflow.workflow import WorkflowExecutor
from tests.functional.fixtures.test_action import ActionProvider


class MockWorkflowAction(ActionProvider):
    """Mock action for workflow testing."""

    name = "mock-workflow-action"
    version = "1.0.0"
    description = "Mock action for workflow testing"

    def _execute(
        self, action: str, parameters: dict, mode: str, context, logger
    ) -> ActionResult:
        metadata = {
            "mode": mode,
            "parameters": parameters,
        }

        if context:
            metadata["context_mode"] = context.mode

        status = "validated" if mode == "dry-run" else "executed"
        return (status, metadata, [])


class MockFailingAction(ActionProvider):
    """Mock action that fails during execution."""

    name = "mock-failing-action"
    version = "1.0.0"
    description = "Mock action that always fails"

    def _execute(
        self, action: str, parameters: dict, mode: str, context, logger
    ) -> ActionResult:
        raise ActionExecutionError("Mock action failure")


@pytest.fixture
def executor() -> WorkflowExecutor:
    """Pytest fixture for executor setup."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["mock_workflow_action"] = (
        MockWorkflowAction
    )
    executor.action_registry._actions["mock_failing_action"] = (
        MockFailingAction
    )
    return executor
