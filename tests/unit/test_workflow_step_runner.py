"""Unit tests for the workflow step runner (step_runner.py)."""

from pathlib import Path

import pytest

from causaliq_workflow.workflow import (
    WorkflowExecutionError,
    WorkflowExecutor,
)


# Test error when action produces objects but no workflow cache is open.
def test_execute_workflow_objects_without_cache_raises_error(
    executor: WorkflowExecutor,
) -> None:
    """Action producing objects without a cache destination raises error."""
    workflow = {
        "steps": [
            {
                "uses": "mock_object_action",
                "name": "Produce Objects",
                "with": {"action": "test"},
                # Note: no 'output' specified, so no cache is created
            }
        ],
    }
    with pytest.raises(
        WorkflowExecutionError,
        match="produced objects but no workflow cache is open",
    ):
        executor.execute_workflow(workflow, mode="run")


# Test step logging reports a skipped step.
def test_execute_workflow_logs_skipped_step(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_core import CausalIQActionProvider

    class MockSkippingAction(CausalIQActionProvider):
        name = "mock-skipping"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            return ("skipped", {"reason": "recorded failure"}, [])

    executor.action_registry._actions["mock_skipping"] = MockSkippingAction
    statuses = []

    def step_logger(
        action_method, step_name, status, matrix_values, **_: object
    ):
        statuses.append(status)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_skipping",
                "name": "Test Step",
                "with": {
                    "action": "learn_graph",
                    "output": str(tmp_path / "out.db"),
                },
            }
        ],
    }
    executor.execute_workflow(workflow, mode="run", step_logger=step_logger)

    assert statuses == ["SKIPPED"]


# Test dry-run reports would_skip when the output cache holds the entry.
def test_execute_workflow_dry_run_skips_existing_cache_entry(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    db_path = tmp_path / "out.db"
    with WorkflowCache(str(db_path)) as cache:
        entry = CacheEntry()
        entry.add_object("dag", "graphml", "<graphml/>", "learn_graph")
        cache.put_typed({"dataset": "asia"}, entry)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "output": str(db_path)},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")

    assert results[0]["steps"]["Test Step"]["status"] == "would_skip"
