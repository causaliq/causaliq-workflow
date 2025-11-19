"""
Additional unit tests for WorkflowExecutor to achieve 100% coverage.

Tests execution paths, error handling, and edge cases.
"""

import pytest

from causaliq_workflow.action import ActionExecutionError
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor

# Import CausalIQAction from test fixtures
from tests.functional.fixtures.test_action import CausalIQAction


class MockWorkflowCausalIQAction(CausalIQAction):
    """Mock action for workflow testing."""

    name = "mock-workflow-action"
    version = "1.0.0"
    description = "Mock action for workflow testing"

    def run(self, inputs: dict, **kwargs) -> dict:
        mode = kwargs.get("mode", "run")
        context = kwargs.get("context")
        kwargs.get("logger")

        # Include context information to test CLI params via variable
        # resolution
        result = {
            "status": "validated" if mode == "dry-run" else "executed",
            "mode": mode,
            "inputs": inputs,
        }

        if context:
            result["context_mode"] = context.mode

        return result


class MockFailingCausalIQAction(CausalIQAction):
    """Mock action that fails during execution."""

    name = "mock-failing-action"
    version = "1.0.0"
    description = "Mock action that always fails"

    def run(self, inputs: dict, **kwargs) -> dict:
        raise ActionExecutionError("Mock action failure")


# Pytest fixture for executor setup
@pytest.fixture
def executor():
    executor = WorkflowExecutor()
    executor.action_registry._actions["mock_workflow_action"] = (
        MockWorkflowCausalIQAction
    )
    executor.action_registry._actions["mock_failing_action"] = (
        MockFailingCausalIQAction
    )
    return executor


# Test resolving template variables in a dictionary
def test_resolve_template_variables_dict(executor):
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


# Test resolving template variables in a list
def test_resolve_template_variables_list(executor):
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


# Test resolving template variables in a string
def test_resolve_template_variables_string(executor):
    variables = {"name": "test", "version": "1.0", "extra": "value"}
    obj = "{{name}}_v{{version}}_{{extra}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_v1.0_value.log"


# Test resolving template variables with a missing variable
def test_resolve_template_variables_string_missing_variable(executor):
    variables = {"name": "test"}
    obj = "{{name}}_{{missing}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_{{missing}}.log"


# Test resolving template variables with non-string types
def test_resolve_template_variables_non_string_types(executor):
    variables = {"key": "value"}
    assert executor._resolve_template_variables(42, variables) == 42
    assert executor._resolve_template_variables(True, variables) is True
    assert executor._resolve_template_variables(None, variables) is None
    assert executor._resolve_template_variables(3.14, variables) == 3.14

    def test_validate_workflow_actions_failure(self):
        """Test _validate_workflow_actions when action validation fails."""
        workflow = {"steps": [{"uses": "unknown-action", "name": "Test Step"}]}

        with pytest.raises(
            WorkflowExecutionError, match="Action validation failed"
        ):
            self.executor._validate_workflow_actions(workflow, "run")


# Test validation failure for unknown action
def test_validate_workflow_actions_failure(executor):
    workflow = {"steps": [{"uses": "unknown-action", "name": "Test Step"}]}
    with pytest.raises(
        WorkflowExecutionError, match="Action validation failed"
    ):
        executor._validate_workflow_actions(workflow, "run")

    def test_validate_workflow_actions_dry_run_mode_skip(self):
        """Test _validate_workflow_actions skips dry-run validation when mode
        is dry-run."""
        workflow = {
            "steps": [
                {
                    "uses": "mock_workflow_action",
                    "name": "Test Step",
                    "with": {"param": "value"},
                }
            ]
        }

        # Should not raise an error, dry-run validation is skipped when mode
        # is already dry-run
        self.executor._validate_workflow_actions(workflow, "dry-run")


# Test skipping validation in dry-run mode
def test_validate_workflow_actions_dry_run_mode_skip(executor):
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

    def test_validate_workflow_actions_full_validation_failure(self):
        """Test _validate_workflow_actions when dry-run execution fails."""
        workflow = {
            "steps": [{"uses": "mock_failing_action", "name": "Failing Step"}]
        }

        with pytest.raises(
            WorkflowExecutionError, match="Workflow dry-run validation failed"
        ):
            self.executor._validate_workflow_actions(workflow, "run")


# Test validation failure when dry-run execution fails
def test_validate_workflow_actions_full_validation_failure(executor):
    workflow = {
        "steps": [{"uses": "mock_failing_action", "name": "Failing Step"}]
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow dry-run validation failed"
    ):
        executor._validate_workflow_actions(workflow, "run")

    def test_execute_workflow_dry_run_mode(self):
        """Test execute_workflow in dry-run mode."""
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

        results = self.executor.execute_workflow(workflow, mode="dry-run")

        assert len(results) == 1
        assert "job" in results[0]
        assert "steps" in results[0]
        assert "Test Step" in results[0]["steps"]
        step_result = results[0]["steps"]["Test Step"]
        assert step_result["status"] == "validated"
        assert step_result["mode"] == "dry-run"


# Test executing workflow in dry-run mode
def test_execute_workflow_dry_run_mode(executor):
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

    def test_execute_workflow_run_mode(self):
        """Test execute_workflow in run mode."""
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

        results = self.executor.execute_workflow(workflow, mode="run")

        assert len(results) == 1
        assert "job" in results[0]
        assert "steps" in results[0]
        assert "Test Step" in results[0]["steps"]
        step_result = results[0]["steps"]["Test Step"]
        assert step_result["status"] == "executed"
        assert step_result["mode"] == "run"
        assert step_result["inputs"]["input"] == "asia.csv"


# Test executing workflow in run mode
def test_execute_workflow_run_mode(executor):
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
    assert step_result["inputs"]["input"] == "asia.csv"

    def test_execute_workflow_with_cli_params(self):
        """Test execute_workflow with CLI parameters."""
        workflow = {
            "id": "test-workflow",
            "matrix": {"dataset": ["asia"]},
            "steps": [
                {
                    "uses": "mock_workflow_action",
                    "name": "Test Step",
                    "with": {
                        "input": "{{dataset}}.csv",
                        "extra_param": "{{extra_param}}",  # CLI template param
                    },
                }
            ],
        }

        cli_params = {"extra_param": "cli_value"}

        results = self.executor.execute_workflow(
            workflow, mode="run", cli_params=cli_params
        )

        assert len(results) == 1
        step_result = results[0]["steps"]["Test Step"]
        # CLI params should be resolved via template variables
        assert "extra_param" in step_result["inputs"]
        assert step_result["inputs"]["extra_param"] == "cli_value"


# Test executing workflow with CLI parameters
def test_execute_workflow_with_cli_params(executor):
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "input": "{{dataset}}.csv",
                    "extra_param": "{{extra_param}}",  # CLI template param
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
    assert "extra_param" in step_result["inputs"]
    assert step_result["inputs"]["extra_param"] == "cli_value"

    def test_execute_workflow_multiple_matrix_combinations(self):
        """Test execute_workflow with multiple matrix combinations."""
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

        results = self.executor.execute_workflow(workflow, mode="run")

        # Should have 4 results (2 datasets × 2 algorithms)
        assert len(results) == 4

        # Check that all combinations are present
        combinations = []
        for result in results:
            step_result = result["steps"]["Test Step"]
            combinations.append(
                (
                    step_result["inputs"]["dataset"],
                    step_result["inputs"]["algorithm"],
                )
            )

        expected_combinations = [
            ("asia", "pc"),
            ("asia", "ges"),
            ("cancer", "pc"),
            ("cancer", "ges"),
        ]

        assert set(combinations) == set(expected_combinations)


# Test executing workflow with multiple matrix combinations
def test_execute_workflow_multiple_matrix_combinations(executor):
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
                step_result["inputs"]["dataset"],
                step_result["inputs"]["algorithm"],
            )
        )
    expected_combinations = [
        ("asia", "pc"),
        ("asia", "ges"),
        ("cancer", "pc"),
        ("cancer", "ges"),
    ]
    assert set(combinations) == set(expected_combinations)


# Test workflow execution error when action fails
def test_execute_workflow_action_execution_error(executor):
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [{"uses": "mock_failing_action", "name": "Failing Step"}],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow execution failed"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test workflow execution error for missing action
def test_execute_workflow_missing_action(executor):
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
