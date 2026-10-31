"""Unit tests for WorkflowExecutor entry points and job sequencing."""

import pytest

from causaliq_workflow.workflow import (
    WorkflowExecutionError,
    WorkflowExecutor,
)


# Test executing workflow in dry-run mode.
def test_execute_workflow_dry_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "would_execute"


# Test executing workflow in run mode.
def test_execute_workflow_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "executed"
    assert step_result["mode"] == "run"
    assert step_result["parameters"]["input"] == "asia.csv"


# Test executing workflow with CLI parameters.
def test_execute_workflow_with_cli_params(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "action": "test",
                    "input": "{{dataset}}.csv",
                    "extra_param": "{{extra_param}}",
                },
            }
        ],
    }
    cli_params = {"extra_param": "cli_value"}
    results = executor.execute_workflow(
        workflow, mode="run", cli_params=cli_params
    )
    assert len(results) == 1
    step_result = results[0]["steps"]["Test Step"]
    assert "extra_param" in step_result["parameters"]
    assert step_result["parameters"]["extra_param"] == "cli_value"


# Test executing workflow with multiple matrix combinations.
def test_execute_workflow_multiple_matrix(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "action": "test",
                    "dataset": "{{dataset}}",
                    "algorithm": "{{algorithm}}",
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 4
    combinations = []
    for result in results:
        step_result = result["steps"]["Test Step"]
        combinations.append(
            (
                step_result["parameters"]["dataset"],
                step_result["parameters"]["algorithm"],
            )
        )
    expected_combinations = [
        ("asia", "pc"),
        ("asia", "ges"),
        ("cancer", "pc"),
        ("cancer", "ges"),
    ]
    assert set(combinations) == set(expected_combinations)


# Test workflow execution error when action fails.
def test_execute_workflow_action_execution_error(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_failing_action",
                "name": "Failing Step",
                "with": {"action": "test"},
            }
        ],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow execution failed"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test workflow execution error for missing action.
def test_execute_workflow_missing_action(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "nonexistent-action",
                "name": "Missing Action Step",
                "with": {"action": "test"},
            }
        ],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Action 'nonexistent-action' not found"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test matrix variables are NOT passed implicitly to actions (explicit only).
def test_execute_workflow_matrix_params_require_explicit_specification(
    executor: WorkflowExecutor,
) -> None:
    """Matrix variables should NOT be passed to actions without {{var}}."""
    workflow = {
        "matrix": {
            "network": ["asia", "alarm"],
            "sample_size": [100, 500],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                # Note: no {{network}} or {{sample_size}} templates
                "with": {"action": "test", "explicit_param": "value"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")

    # Should have 4 combinations (2 networks × 2 sample_sizes)
    assert len(results) == 4

    # Verify each result does NOT have implicit matrix params
    for result in results:
        step_result = result["steps"]["Test Step"]
        params = step_result["parameters"]

        # Explicit param should be present
        assert params["explicit_param"] == "value"

        # Matrix variables should NOT be implicitly passed
        assert "network" not in params
        assert "sample_size" not in params


# Test matrix params are passed when explicitly specified via templates.
def test_execute_workflow_explicit_matrix_params_via_templates(
    executor: WorkflowExecutor,
) -> None:
    """Matrix variables passed via {{var}} templates should work."""
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                # Explicit network param via template
                "with": {"action": "test", "network": "{{network}}"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1

    step_result = results[0]["steps"]["Test Step"]
    params = step_result["parameters"]

    # Explicit param via template should be present
    assert params["network"] == "asia"
