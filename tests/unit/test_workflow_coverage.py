"""Unit tests for WorkflowExecutor coverage."""

import pytest

from causaliq_workflow.action import ActionExecutionError
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor
from tests.functional.fixtures.test_action import ActionProvider


class MockWorkflowAction(ActionProvider):
    """Mock action for workflow testing."""

    name = "mock-workflow-action"
    version = "1.0.0"
    description = "Mock action for workflow testing"

    def run(self, action: str, parameters: dict, **kwargs) -> dict:
        mode = kwargs.get("mode", "run")
        context = kwargs.get("context")
        kwargs.get("logger")

        result = {
            "status": "validated" if mode == "dry-run" else "executed",
            "mode": mode,
            "parameters": parameters,
        }

        if context:
            result["context_mode"] = context.mode

        return result


class MockFailingAction(ActionProvider):
    """Mock action that fails during execution."""

    name = "mock-failing-action"
    version = "1.0.0"
    description = "Mock action that always fails"

    def run(self, action: str, parameters: dict, **kwargs) -> dict:
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


# Test resolving template variables in a dictionary.
def test_resolve_template_variables_dict(executor: WorkflowExecutor) -> None:
    variables = {"dataset": "asia", "algorithm": "pc"}
    obj = {
        "input": "{{dataset}}.csv",
        "output": "results/{{algorithm}}/{{dataset}}.xml",
        "nested": {"path": "/data/{{dataset}}/{{algorithm}}"},
    }
    result = executor._resolve_template_variables(obj, variables)
    assert result["input"] == "asia.csv"
    assert result["output"] == "results/pc/asia.xml"
    assert result["nested"]["path"] == "/data/asia/pc"


# Test resolving template variables in a list.
def test_resolve_template_variables_list(executor: WorkflowExecutor) -> None:
    variables = {"dataset": "asia", "num": "42"}
    obj = [
        "{{dataset}}.csv",
        "file_{{num}}.txt",
        {"name": "{{dataset}}_{{num}}"},
    ]
    result = executor._resolve_template_variables(obj, variables)
    assert result[0] == "asia.csv"
    assert result[1] == "file_42.txt"
    assert result[2]["name"] == "asia_42"


# Test resolving template variables in a string.
def test_resolve_template_variables_string(executor: WorkflowExecutor) -> None:
    variables = {"name": "test", "version": "1.0", "extra": "value"}
    obj = "{{name}}_v{{version}}_{{extra}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_v1.0_value.log"


# Test resolving template variables with a missing variable.
def test_resolve_template_variables_missing(
    executor: WorkflowExecutor,
) -> None:
    variables = {"name": "test"}
    obj = "{{name}}_{{missing}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_{{missing}}.log"


# Test resolving template variables with non-string types.
def test_resolve_template_variables_non_string(
    executor: WorkflowExecutor,
) -> None:
    variables = {"key": "value"}
    assert executor._resolve_template_variables(42, variables) == 42
    assert executor._resolve_template_variables(True, variables) is True
    assert executor._resolve_template_variables(None, variables) is None
    assert executor._resolve_template_variables(3.14, variables) == 3.14


# Test validation failure for unknown action.
def test_validate_workflow_actions_failure(
    executor: WorkflowExecutor,
) -> None:
    workflow = {"steps": [{"uses": "unknown-action", "name": "Test Step"}]}
    with pytest.raises(
        WorkflowExecutionError, match="Action validation failed"
    ):
        executor._validate_workflow_actions(workflow, "run")


# Test skipping validation in dry-run mode.
def test_validate_workflow_actions_dry_run_skip(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"param": "value"},
            }
        ]
    }
    executor._validate_workflow_actions(workflow, "dry-run")


# Test validation failure when dry-run execution fails.
def test_validate_workflow_actions_full_validation_failure(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "steps": [{"uses": "mock_failing_action", "name": "Failing Step"}]
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow dry-run validation failed"
    ):
        executor._validate_workflow_actions(workflow, "run")


# Test executing workflow in dry-run mode.
def test_execute_workflow_dry_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "validated"
    assert step_result["mode"] == "dry-run"


# Test executing workflow in run mode.
def test_execute_workflow_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"input": "{{dataset}}.csv"},
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
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
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
        "id": "test-workflow",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
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
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [{"uses": "mock_failing_action", "name": "Failing Step"}],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow execution failed"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test workflow execution error for missing action.
def test_execute_workflow_missing_action(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {"uses": "nonexistent-action", "name": "Missing Action Step"}
        ],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Action 'nonexistent-action' not found"
    ):
        executor.execute_workflow(workflow, mode="run")
