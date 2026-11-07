"""Unit tests for the workflow step runner (step_runner.py)."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

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

    assert statuses == ["RUNNING", "SKIPPED"]


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


def _write_cached_output(db_path: Path, matrix_values: dict) -> None:
    """Write one typed entry to an output cache."""
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    with WorkflowCache(str(db_path)) as cache:
        entry = CacheEntry()
        entry.add_object("dag", "graphml", "<graphml/>", "learn_graph")
        cache.put_typed(matrix_values, entry)


# Test run mode skips a cached entry before scanning its inputs.
def test_run_skips_cached_entry_before_scanning_inputs(
    executor: WorkflowExecutor,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    input_path = tmp_path / "in.db"
    output_path = tmp_path / "out.db"
    with WorkflowCache(str(input_path)) as cache:
        cache.put({"dataset": "asia"}, CacheEntry(metadata={}))
    _write_cached_output(output_path, {"dataset": "asia"})

    spy = mocker.spy(WorkflowExecutor, "_scan_aggregation_inputs")
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "action": "test",
                    "input": str(input_path),
                    "output": str(output_path),
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run", validate=False)

    assert results[0]["steps"]["Test Step"] == {
        "status": "skipped",
        "reason": "cached",
    }
    assert spy.call_count == 0


# Test run mode executes a step whose output entry is absent.
def test_run_executes_step_without_cached_entry(
    executor: WorkflowExecutor,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    input_path = tmp_path / "in.db"
    with WorkflowCache(str(input_path)) as cache:
        cache.put({"dataset": "asia"}, CacheEntry(metadata={}))

    spy = mocker.spy(WorkflowExecutor, "_scan_aggregation_inputs")
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "action": "test",
                    "input": str(input_path),
                    "output": str(tmp_path / "out.db"),
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run", validate=False)

    assert results[0]["steps"]["Test Step"]["status"] != "skipped"
    assert spy.call_count == 1


# Test force mode runs a step whose output entry already exists.
def test_force_runs_cached_entry(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    output_path = tmp_path / "out.db"
    _write_cached_output(output_path, {"dataset": "asia"})

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "output": str(output_path)},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="force", validate=False)

    assert results[0]["steps"]["Test Step"]["status"] != "skipped"
