"""
Unit tests for WorkflowContext matrix field setup and propagation.

Tests that verify the matrix definition is correctly passed through the
workflow execution pipeline to actions via WorkflowContext.
"""

import pytest

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.workflow import WorkflowExecutor

# Import CausalIQAction from test fixtures
from tests.functional.fixtures.test_action import CausalIQAction


class MatrixTestAction(CausalIQAction):
    """Test action that captures WorkflowContext matrix for verification."""

    name = "matrix-test-action"
    version = "1.0.0"
    description = "Test action that captures matrix context"

    def run(self, inputs: dict, **kwargs) -> dict:
        mode = kwargs.get("mode", "run")
        context = kwargs.get("context")

        # Capture the context matrix for testing
        result = {
            "status": "success",
            "mode": mode,
            "inputs": inputs,
        }

        if context:
            result["context_matrix"] = context.matrix
            result["context_mode"] = context.mode

        return result


@pytest.fixture
def executor():
    executor = WorkflowExecutor()
    executor.action_registry._actions["matrix_test_action"] = MatrixTestAction
    return executor


# Test simple matrix definition storage in WorkflowContext
def test_workflow_context_matrix_simple():
    """Test WorkflowContext matrix field with simple matrix definition."""
    matrix_def = {"dataset": ["asia", "cancer"]}

    context = WorkflowContext(
        mode="run",
        matrix=matrix_def,
    )

    # Verify matrix is stored correctly
    assert context.matrix == matrix_def
    assert context.matrix["dataset"] == ["asia", "cancer"]


# Test complex multi-dimensional matrix preservation
def test_workflow_context_matrix_complex():
    """Test WorkflowContext matrix with complex multi-dimensional matrix."""
    matrix_def = {
        "dataset": ["asia", "cancer", "earthquake"],
        "algorithm": ["pc", "ges", "lingam"],
        "alpha": [0.01, 0.05, 0.1],
    }

    context = WorkflowContext(
        mode="dry-run",
        matrix=matrix_def,
    )

    # Verify complete matrix is preserved
    assert context.matrix == matrix_def
    assert len(context.matrix["dataset"]) == 3
    assert len(context.matrix["algorithm"]) == 3
    assert len(context.matrix["alpha"]) == 3


# Test empty matrix handling in WorkflowContext
def test_workflow_context_matrix_empty():
    """Test WorkflowContext matrix field with empty matrix."""
    matrix_def = {}

    context = WorkflowContext(
        mode="run",
        matrix=matrix_def,
    )

    assert context.matrix == {}


# Test matrix propagation from WorkflowExecutor to WorkflowContext
def test_workflow_executor_passes_matrix_to_context(executor):
    """Test WorkflowExecutor correctly passes matrix to WorkflowContext."""
    workflow = {
        "id": "matrix-test-workflow",
        "matrix": {"dataset": ["asia", "cancer"], "algorithm": ["pc", "ges"]},
        "steps": [
            {
                "name": "Matrix Test Step",
                "uses": "matrix_test_action",
                "with": {
                    "data_path": "/test/{{dataset}}.csv",
                    "algorithm": "{{algorithm}}",
                },
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="run")

    # Should have 4 results (2x2 matrix)
    assert len(results) == 4

    # Check that each job received the complete matrix in context
    for result in results:
        step_result = result["steps"]["Matrix Test Step"]

        # Verify the action received the complete matrix definition
        assert "context_matrix" in step_result
        received_matrix = step_result["context_matrix"]

        # Should be the complete matrix, not just the current job values
        assert received_matrix == workflow["matrix"]
        assert "dataset" in received_matrix
        assert "algorithm" in received_matrix
        assert received_matrix["dataset"] == ["asia", "cancer"]
        assert received_matrix["algorithm"] == ["pc", "ges"]


# Test matrix context with workflows that have no matrix defined
def test_workflow_executor_matrix_passed_to_single_job(executor):
    """Test matrix passed to context even with single job (no matrix)."""
    workflow = {
        "id": "single-job-workflow",
        # No matrix defined - should result in empty matrix
        "steps": [
            {
                "name": "Single Job Step",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/data.csv"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="dry-run")

    # Should have 1 result
    assert len(results) == 1

    step_result = results[0]["steps"]["Single Job Step"]

    # Should receive empty matrix
    assert "context_matrix" in step_result
    assert step_result["context_matrix"] == {}


# Test matrix access for cross-job optimization decisions
def test_matrix_available_for_action_optimization(executor):
    """Test actions can use matrix for cross-job optimization decisions."""
    # Large matrix that might warrant optimization
    workflow = {
        "id": "optimization-test-workflow",
        "matrix": {
            "dataset": ["asia", "cancer", "earthquake", "sachs", "child"],
            "algorithm": ["pc", "ges", "lingam", "notears"],
        },
        "steps": [
            {
                "name": "Optimization Test",
                "uses": "matrix_test_action",
                "with": {"data_path": "/data/{{dataset}}.csv"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="dry-run")

    # Should have 20 results (5x4 matrix)
    assert len(results) == 20

    # Every job should receive the same complete matrix for optimization
    expected_matrix = workflow["matrix"]

    for result in results:
        step_result = result["steps"]["Optimization Test"]
        received_matrix = step_result["context_matrix"]

        # Each action gets the complete matrix for optimization decisions
        assert received_matrix == expected_matrix

        # Action could decide: "5 datasets * 4 algorithms = 20 jobs,
        # worth pre-loading all datasets into memory"
        total_jobs = len(received_matrix["dataset"]) * len(
            received_matrix["algorithm"]
        )
        assert total_jobs == 20


# Test data type preservation in matrix definitions
def test_matrix_preserves_data_types(executor):
    """Test that matrix preserves various data types correctly."""
    workflow = {
        "id": "data-types-test",
        "matrix": {
            "dataset": ["asia", "cancer"],  # strings
            "alpha": [0.01, 0.05, 0.1],  # floats
            "max_iter": [100, 1000],  # ints
            "use_cache": [True, False],  # booleans
        },
        "steps": [
            {
                "name": "Data Types Test",
                "uses": "matrix_test_action",
                "with": {"alpha": "{{alpha}}", "max_iter": "{{max_iter}}"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="run")

    # Should have 24 results (2*3*2*2)
    assert len(results) == 24

    # Check first result for data type preservation
    step_result = results[0]["steps"]["Data Types Test"]
    received_matrix = step_result["context_matrix"]

    # Verify data types are preserved
    assert isinstance(received_matrix["alpha"][0], float)
    assert isinstance(received_matrix["max_iter"][0], int)
    assert isinstance(received_matrix["use_cache"][0], bool)
    assert isinstance(received_matrix["dataset"][0], str)


# Test mode parameter passed correctly to actions in dry-run mode
def test_mode_parameter_dry_run_execution(executor):
    """Test mode parameter correctly passed to actions in dry-run mode."""
    workflow = {
        "id": "mode-test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "Mode Test Step",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert len(results) == 1
    step_result = results[0]["steps"]["Mode Test Step"]

    # Verify both mode parameter and context.mode are set to dry-run
    assert step_result["mode"] == "dry-run"
    assert step_result["context_mode"] == "dry-run"


# Test mode parameter passed correctly to actions in run mode
def test_mode_parameter_run_execution(executor):
    """Test mode parameter correctly passed to actions in run mode."""
    workflow = {
        "id": "mode-test-workflow",
        "matrix": {"dataset": ["cancer"]},
        "steps": [
            {
                "name": "Mode Test Step",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="run")

    assert len(results) == 1
    step_result = results[0]["steps"]["Mode Test Step"]

    # Verify both mode parameter and context.mode are set to run
    assert step_result["mode"] == "run"
    assert step_result["context_mode"] == "run"


# Test mode parameter consistency across multiple matrix jobs
def test_mode_parameter_consistency_across_matrix_jobs(executor):
    """Test mode parameter consistent across all matrix job executions."""
    workflow = {
        "id": "mode-consistency-test",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "name": "Consistency Test",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="dry-run")

    # Should have 4 results (2x2 matrix)
    assert len(results) == 4

    # Every job should receive the same mode
    for result in results:
        step_result = result["steps"]["Consistency Test"]
        assert step_result["mode"] == "dry-run"
        assert step_result["context_mode"] == "dry-run"


# Test mode parameter with compare mode (future mode)
def test_mode_parameter_compare_execution(executor):
    """Test mode parameter correctly passed with compare mode."""
    workflow = {
        "id": "compare-mode-test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "Compare Test",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="compare")

    assert len(results) == 1
    step_result = results[0]["steps"]["Compare Test"]

    # Verify compare mode is passed correctly
    assert step_result["mode"] == "compare"
    assert step_result["context_mode"] == "compare"


# Test that action receives mode even when no context is provided
def test_mode_parameter_without_context():

    action = MatrixTestAction()

    # Call action directly without context
    result = action.run(
        inputs={"data_path": "/test/data.csv"},
        mode="dry-run",
        context=None,
    )

    # Should receive the mode parameter
    assert result["mode"] == "dry-run"
    # No context provided, so context_mode shouldn't be in result
    assert "context_mode" not in result
